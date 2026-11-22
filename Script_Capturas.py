from collections import Counter
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import os
from statistics import mean
import time

import mysql.connector as mysql
from mysql.connector import Error as MySQLError
import psutil
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


# CONFIGURAÇÃO DO BANCO — preencha com os dados do seu ambiente.
# Use o IP/nome do servidor MySQL; 127.0.0.1 só funciona se o MySQL
# estiver instalado nesta mesma máquina.
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "aluno",
    "password": "Seg2805/rocha",
    "database": "optikus",
}

# Deve corresponder exatamente ao equipamento.numero_serie no banco.
# Configure um número de série diferente em cada servidor.
NUMERO_SERIE = "LEGADO-SRV-1"

INTERVALO_SEGUNDOS = 60
TIPOS_METRICAS = ("CPU", "Memoria", "Disco")
CENTESIMO = Decimal("0.01")

CAMINHO_DISCO = (
    os.environ.get("SystemDrive", "C:") + "\\" if os.name == "nt" else "/"
)


def coletar_metricas():
  cpu = psutil.cpu_percent(interval=INTERVALO_SEGUNDOS)
  memoria = psutil.virtual_memory().percent
  disco = psutil.disk_usage(CAMINHO_DISCO).percent

  return {
      "CPU": Decimal(str(cpu)).quantize(CENTESIMO, rounding=ROUND_HALF_UP),
      "Memoria": Decimal(str(memoria)).quantize(
          CENTESIMO, rounding=ROUND_HALF_UP
      ),
      "Disco": Decimal(str(disco)).quantize(CENTESIMO, rounding=ROUND_HALF_UP),
  }


def buscar_capturas_com_parametros_ativos(cursor, valores):
  cursor.execute(
      """
        SELECT
            componente.id AS id_componente,
            tipo_componente.nome AS tipo,
            parametro_limite.id AS id_parametro,
            parametro_limite.valor_minimo,
            parametro_limite.valor_maximo,
            parametro_limite.criticidade
        FROM servidor
        JOIN equipamento
            ON equipamento.id = servidor.id_equipamento
        JOIN componente
            ON componente.id_servidor = servidor.id
            AND componente.status = 'ATIVO'
        JOIN tipo_componente
            ON tipo_componente.id = componente.id_tipo
        JOIN parametro_limite
            ON parametro_limite.id_componente = componente.id
            AND parametro_limite.ativo = 1
        WHERE equipamento.numero_serie = %s
            AND tipo_componente.nome IN ('CPU', 'Memoria', 'Disco')
        ORDER BY tipo_componente.nome, parametro_limite.valor_minimo
        """,
      (NUMERO_SERIE,),
  )

  componentes = {}

  for linha in cursor.fetchall():
    tipo = linha["tipo"]
    id_componente = int(linha["id_componente"])
    componente = componentes.get(tipo)

    if componente is None:
      componente = {"id": id_componente, "faixas": []}
      componentes[tipo] = componente
    elif componente["id"] != id_componente:
      raise RuntimeError(
          "Há mais de um componente ativo do tipo "
          + tipo
          + " para o número de série "
          + NUMERO_SERIE
      )

    componente["faixas"].append({
        "id_parametro": int(linha["id_parametro"]),
        "minimo": Decimal(str(linha["valor_minimo"])),
        "maximo": Decimal(str(linha["valor_maximo"])),
        "criticidade": linha["criticidade"],
    })

  ausentes = [tipo for tipo in TIPOS_METRICAS if tipo not in componentes]
  if ausentes:
    raise RuntimeError(
        "Sem componente ou limite ativo para: "
        + ", ".join(ausentes)
        + ". Confira o servidor e os limites cadastrados no banco."
    )

  capturas = []

  for tipo in TIPOS_METRICAS:
    componente = componentes[tipo]
    valor = valores[tipo]

    faixas_correspondentes = [
        faixa
        for faixa in componente["faixas"]
        if faixa["minimo"] <= valor <= faixa["maximo"]
    ]

    if len(faixas_correspondentes) != 1:
      raise RuntimeError(
          "O valor de "
          + tipo
          + " ("
          + str(valor)
          + "%) não corresponde a exatamente um limite ativo."
      )

    faixa = faixas_correspondentes[0]
    capturas.append((
        valor,
        componente["id"],
        faixa["id_parametro"],
        tipo,
        faixa["criticidade"],
    ))

  return capturas


def salvar_capturas(valores):
  conexao = mysql.connect(**DB_CONFIG)
  cursor = None

  try:
    cursor = conexao.cursor(dictionary=True)
    capturas = buscar_capturas_com_parametros_ativos(cursor, valores)
    momento = datetime.now()

    cursor.executemany(
        """
            INSERT INTO captura (valor, id_componente, parametroId, criado_em)
            VALUES (%s, %s, %s, %s)
            """,
        [
            (valor, id_componente, id_parametro, momento)
            for valor, id_componente, id_parametro, _, _ in capturas
        ],
    )

    conexao.commit()
    return capturas, momento

  except Exception:
    conexao.rollback()
    raise

  finally:
    if cursor is not None:
      cursor.close()
    conexao.close()


def gerar_relatorio(historico):
  if not historico:
    print("Nenhuma captura realizada para gerar relatório.")
    return

  os.makedirs("relatorios", exist_ok=True)
  arquivo = f"relatorios/relatorio_{NUMERO_SERIE}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

  pdf = SimpleDocTemplate(arquivo)
  estilos = getSampleStyleSheet()
  conteudo = []

  def adicionar(texto, estilo="Normal"):
    conteudo.append(Paragraph(texto, estilos[estilo]))
    conteudo.append(Spacer(1, 12))

  adicionar(f"RELATÓRIO DE MONITORAMENTO - {NUMERO_SERIE}", "Title")

  adicionar("1. Período de monitoramento", "Heading2")
  adicionar(f"Início: {historico[0]['horario']}")
  adicionar(f"Última captura: {historico[-1]['horario']}")
  adicionar(f"Total de ciclos: {len(historico)}")

  componentes_nomes = {
      "CPU": "CPU",
      "Memoria": "Memória (RAM)",
      "Disco": "Disco",
  }

  adicionar("2. Estatísticas dos componentes", "Heading2")

  tabela_dados = [["Componente", "Mínimo", "Máximo", "Média", "Status no Pico"]]

  medias = {}
  componentes_risco = []

  for chave, nome_exibicao in componentes_nomes.items():
    valores = [c[chave]["valor"] for c in historico]

    minimo = min(valores)
    maximo = max(valores)
    media = mean(valores)
    medias[nome_exibicao] = media

    # Encontra o registro de maior valor para pegar o horário e a criticidade do banco
    pico = max(historico, key=lambda c: c[chave]["valor"])
    status_pico = pico[chave]["criticidade"]

    if status_pico.upper() != "NORMAL":
      componentes_risco.append((nome_exibicao, status_pico))

    tabela_dados.append([
        nome_exibicao,
        f"{minimo:.2f}%",
        f"{maximo:.2f}%",
        f"{media:.2f}%",
        status_pico,
    ])

    adicionar(
        f"{nome_exibicao}: maior captura registrada em {pico['horario']}"
    )

  tabela = Table(tabela_dados)
  tabela.setStyle(
      TableStyle([
          ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
          ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
          ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
          ("PADDING", (0, 0), (-1, -1), 8),
      ])
  )

  conteudo.append(tabela)
  conteudo.append(Spacer(1, 20))

  adicionar("3. Distribuição dos status", "Heading2")

  for chave, nome_exibicao in componentes_nomes.items():
    contagem = Counter(c[chave]["criticidade"].upper() for c in historico)
    # Exibe as contagens padrão e quaisquer outras criticidades cadastradas no banco
    status_unicos = list(
        dict.fromkeys(["NORMAL", "ALERTA", "CRÍTICO", *contagem.keys()])
    )
    resumo_status = " | ".join(f"{st}: {contagem[st]}" for st in status_unicos)
    adicionar(f"{nome_exibicao}: {resumo_status}")

  adicionar("4. Análise dos componentes", "Heading2")

  saudavel = min(medias, key=medias.get)
  adicionar(
      "Componente com menor utilização média: "
      f"{saudavel} ({medias[saudavel]:.2f}%)."
  )

  if componentes_risco:
    for nome_exibicao, status in componentes_risco:
      adicionar(f"Componente em risco: {nome_exibicao} - {status}")
  else:
    adicionar(
        "Nenhum componente atingiu níveis fora de NORMAL durante o"
        " monitoramento."
    )

  adicionar("5. Conclusão", "Heading2")
  adicionar(
      "A análise considera os percentuais de utilização de CPU, Memória e"
      " Disco coletados no servidor. As criticidades exibidas refletem"
      " diretamente as faixas de parâmetros ativos cadastradas no banco de"
      " dados para cada componente."
  )

  pdf.build(conteudo)
  print(f"Relatório gerado em: {os.path.abspath(arquivo)}")


def main():
  print(
      "Coletor iniciado para "
      + NUMERO_SERIE
      + ". Pressione Ctrl+C para encerrar e gerar o relatório."
  )

  historico_capturas = []

  while True:
    try:
      valores = coletar_metricas()
      capturas, momento = salvar_capturas(valores)

      horario_str = momento.strftime("%d/%m/%Y %H:%M:%S")
      registro_ciclo = {"horario": horario_str}

      print(
          "\n[" + momento.strftime("%Y-%m-%d %H:%M:%S") + "] Captura salva:"
      )

      for valor, _, _, tipo, criticidade in capturas:
        print("  - " + tipo + ": " + str(valor) + "% [" + criticidade + "]")
        registro_ciclo[tipo] = {
            "valor": float(valor),
            "criticidade": criticidade,
        }

      historico_capturas.append(registro_ciclo)

    except KeyboardInterrupt:
      print("\nMonitoramento encerrado pelo usuário.")
      gerar_relatorio(historico_capturas)
      break

    except (
        MySQLError,
        psutil.Error,
        OSError,
        RuntimeError,
        ValueError,
    ) as erro:
      print("Erro ao coletar ou salvar métricas: " + str(erro))
      time.sleep(5)


if __name__ == "__main__":
  main()