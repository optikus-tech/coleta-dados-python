from datetime import datetime
import os
import mysql.connector as m
import psutil as p
from dotenv import load_dotenv
from statistics import mean
from collections import Counter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

load_dotenv()


def inserir(cpu, memoria, disco):
  db = m.connect(
      host=os.getenv("DB_HOST"),
      port=3306,
      user=os.getenv("DB_USER"),
      password=os.getenv("DB_PASSWORD"),
      database=os.getenv("DB_NAME")
  )

  try:
    if db.is_connected():
      with db.cursor() as cursor:
        query = "INSERT INTO captura (valor, id_componente) VALUES (%s, %s)"

        valores = [
            (cpu, 1),
            (memoria, 2),
            (disco, 3),
        ]

        cursor.executemany(query, valores)
        db.commit()
        print("-> Dados inseridos no banco com sucesso.")

  except m.Error as erro:
    print("Erro ao conectar/inserir no banco:", erro)

  finally:
    if db.is_connected():
      db.close()

# Regra simples de discretização de status
def obter_status(percentual):
  if percentual < 80:
    return "NORMAL"
  elif percentual < 90:
    return "ALERTA"
  return "CRÍTICO"

def gerar_relatorio(capturas):
    if not capturas:
        print("Nenhuma captura realizada.")
        return

    os.makedirs("relatorios", exist_ok=True)

    arquivo = f"relatorios/relatorio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    pdf = SimpleDocTemplate(arquivo)
    estilos = getSampleStyleSheet()
    conteudo = []

    def adicionar(texto, estilo="Normal"):
        conteudo.append(Paragraph(texto, estilos[estilo]))
        conteudo.append(Spacer(1, 12))

    adicionar("RELATORIO DE MONITORAMENTO", "Title")

    adicionar("1. Periodo de monitoramento", "Heading2")
    adicionar(f"Inicio: {capturas[0]['horario']}")
    adicionar(f"Ultima captura: {capturas[-1]['horario']}")
    adicionar(f"Total de ciclos: {len(capturas)}")

    componentes = {
        "CPU": "cpu",
        "RAM": "ram",
        "Disco": "disco"
    }

    adicionar("2. Estatisticas dos componentes", "Heading2")

    tabela_dados = [
        ["Componente", "Minimo", "Maximo", "Media", "Status"]
    ]

    medias = {}
    componentes_risco = []

    for nome, chave in componentes.items():
        valores = [c[chave] for c in capturas]

        minimo = min(valores)
        maximo = max(valores)
        media = mean(valores)

        medias[nome] = media

        # Classificacao exclusivamente pela discretizacao
        status = obter_status(maximo)

        if status != "NORMAL":
            componentes_risco.append((nome, status))

        tabela_dados.append([
            nome,
            f"{minimo:.2f}%",
            f"{maximo:.2f}%",
            f"{media:.2f}%",
            status
        ])

        # Horario da maior captura
        pico = max(capturas, key=lambda c: c[chave])

        adicionar(
            f"{nome}: maior captura registrada em "
            f"{pico['horario']}"
        )

    tabela = Table(tabela_dados)

    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 8)
    ]))

    conteudo.append(tabela)
    conteudo.append(Spacer(1, 20))

    adicionar("3. Distribuicao dos status", "Heading2")

    for nome, chave in componentes.items():
        contagem = Counter(
            obter_status(c[chave]) for c in capturas
        )

        adicionar(
            f"{nome}: NORMAL: {contagem['NORMAL']} | "
            f"ALERTA: {contagem['ALERTA']} | "
            f"CRITICO: {contagem['CRÍTICO']}"
        )

    adicionar("4. Analise dos componentes", "Heading2")

    saudavel = min(medias, key=medias.get)

    adicionar(
        f"Componente com menor utilizacao media: "
        f"{saudavel} ({medias[saudavel]:.2f}%)."
    )

    if componentes_risco:
        for nome, status in componentes_risco:
            adicionar(
                f"Componente em risco: {nome} - {status}"
            )
    else:
        adicionar(
            "Nenhum componente atingiu os limites "
            "de ALERTA ou CRITICO."
        )

    adicionar("5. Conclusao", "Heading2")

    adicionar(
        "A analise considera os percentuais de utilizacao "
        "de CPU, RAM e Disco. Os componentes em risco "
        "sao identificados exclusivamente pela discretizacao: "
        "NORMAL abaixo de 80%, ALERTA de 80% a menos de 90% "
        "e CRITICO a partir de 90%."
    )

    pdf.build(conteudo)

    print(f"Relatorio gerado em: {os.path.abspath(arquivo)}")



def main():
  print(
      "Iniciando monitoramento contínuo (capturas a cada 1 minuto). Pressione"
      " Ctrl+C para parar."
  )
  contador = 1

  capturas = []

  while True:
    try:
      agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

      # Coleta CPU (o interval=60 aguarda e calcula o uso durante 1 minuto)
      uso_cpu = p.cpu_percent(interval=60)
      status_cpu = obter_status(uso_cpu)

      # Coleta RAM
      uso_ram = p.virtual_memory().percent
      status_ram = obter_status(uso_ram)

      # Coleta Disco
      caminho_disco = (
          os.environ.get("SystemDrive", "C:") + "\\"
          if os.name == "nt"
          else "/"
      )
      uso_disco = p.disk_usage(caminho_disco).percent
      status_disco = obter_status(uso_disco)

      print(
          f"\n[{agora}] Captura #{contador} realizada:"
          f"\n  • CPU: {uso_cpu}% [{status_cpu}]"
          f"\n  • RAM: {uso_ram}% [{status_ram}]"
          f"\n  • Disco: {uso_disco}% [{status_disco}]"
      )

      # Envia para o MySQL mapeando os componentes pelos IDs corretos
      inserir(uso_cpu, uso_ram, uso_disco)

      capturas.append({
       "horario": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
       "cpu": uso_cpu,
       "ram": uso_ram,
        "disco": uso_disco
     })

      contador += 1



    except KeyboardInterrupt:
      print("\nMonitoramento encerrado pelo usuário.")
      gerar_relatorio(capturas)
      break
    except Exception as e:
      print("Erro inesperado no loop:", e)




if __name__ == "__main__":
  main()