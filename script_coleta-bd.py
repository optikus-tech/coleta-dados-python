import os
import socket
import platform
import psutil as p
import time
from datetime import datetime
import mysql.connector as mysql
import threading
from dotenv import load_dotenv
from tabulate import tabulate

load_dotenv()

EMPRESA_ID = 1

controle_tempo = {
    "cpu_inicio_critico": None,
    "cpu_tempo_seg": 0,
    "memoria_inicio_critico": None,
    "memoria_tempo_seg": 0,
    "disco_inicio_critico": None,
    "disco_tempo_seg": 0
}

def discretizar_cpu(uso_cpu):
    horario_atual = time.time()
    
    if uso_cpu < 80:
        controle_tempo["cpu_inicio_critico"] = None
        controle_tempo["cpu_tempo_seg"] = 0
        return "NORMAL"
        
    elif uso_cpu < 90:
        controle_tempo["cpu_inicio_critico"] = None
        controle_tempo["cpu_tempo_seg"] = 0
        return "ALERTA"
        
    else:
        if controle_tempo["cpu_inicio_critico"] is None:
            controle_tempo["cpu_inicio_critico"] = horario_atual
            
        tempo_decorrido = horario_atual - controle_tempo["cpu_inicio_critico"]
        controle_tempo["cpu_tempo_seg"] = tempo_decorrido
        
        if tempo_decorrido >= 30:
            return "CRÍTICO"
        else:
            return "ALERTA (PICO EM OBSERVAÇÃO)"


def discretizar_memoria(uso_memoria):
    horario_atual = time.time()
    
    if uso_memoria < 80:
        controle_tempo["memoria_inicio_critico"] = None
        controle_tempo["memoria_tempo_seg"] = 0
        return "NORMAL"
        
    elif uso_memoria < 90:
        controle_tempo["memoria_inicio_critico"] = None
        controle_tempo["memoria_tempo_seg"] = 0
        return "ALERTA"
        
    else:
        if controle_tempo["memoria_inicio_critico"] is None:
            controle_tempo["memoria_inicio_critico"] = horario_atual
            
        tempo_decorrido = horario_atual - controle_tempo["memoria_inicio_critico"]
        controle_tempo["memoria_tempo_seg"] = tempo_decorrido
        
        if tempo_decorrido >= 30:
            return "CRÍTICO"
        else:
            return "ALERTA (PICO EM OBSERVAÇÃO)"


def discretizar_disco(uso_disco):
    horario_atual = time.time()
    
    if uso_disco < 80:
        controle_tempo["disco_inicio_critico"] = None
        controle_tempo["disco_tempo_seg"] = 0
        return "NORMAL"
        
    elif uso_disco < 90:
        controle_tempo["disco_inicio_critico"] = None
        controle_tempo["disco_tempo_seg"] = 0
        return "ALERTA"
        
    else:
        if controle_tempo["disco_inicio_critico"] is None:
            controle_tempo["disco_inicio_critico"] = horario_atual
            
        tempo_decorrido = horario_atual - controle_tempo["disco_inicio_critico"]
        controle_tempo["disco_tempo_seg"] = tempo_decorrido
        
        if tempo_decorrido >= 30:
            return "CRÍTICO"
        else:
            return "ALERTA (PICO EM OBSERVAÇÃO)"


def conectar():
    try:
        return mysql.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "grupo_07")
        )
    except Exception as erro:
        print("Erro ao conectar ao banco de dados:", erro)
        raise SystemExit(1)


def salvar_perfil():
    conexao = conectar()
    cursor = conexao.cursor()

    try:
        nome_maquina = socket.gethostname()
        nome_so = platform.system()
        
        try:
            ip_maquina = socket.gethostbyname(nome_maquina)
        except:
            ip_maquina = "127.0.0.1"

        cursor.execute(
            "SELECT id FROM servidor WHERE hostname = %s AND empresa_id = %s",
            (nome_maquina, EMPRESA_ID)
        )
        resultado = cursor.fetchone()

        if resultado:
            servidor_id = resultado[0]
            atualizar = """
                UPDATE servidor SET
                    ip = %s,
                    sistema_operacional = %s
                WHERE id = %s AND empresa_id = %s
            """
            cursor.execute(atualizar, (ip_maquina, nome_so, servidor_id, EMPRESA_ID))
            print("Servidor atualizado com sucesso.")
        else:
            cursor.execute("SELECT COUNT(*) FROM servidor WHERE empresa_id = %s", (EMPRESA_ID,))
            total = cursor.fetchone()[0]
            servidor_id = total + 1

            inserir = """
                INSERT INTO servidor (id, ip, hostname, sistema_operacional, empresa_id)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(inserir, (servidor_id, ip_maquina, nome_maquina, nome_so, EMPRESA_ID))
            print("Servidor registrado com sucesso.")

        componentes_padrao = [(1, "CPU"), (2, "Memoria"), (3, "Disco")]
        
        for comp_id, comp_nome in componentes_padrao:
            cursor.execute(
                "SELECT id FROM componentes WHERE id = %s AND servidor_id = %s AND servidor_empresa_id = %s",
                (comp_id, servidor_id, EMPRESA_ID)
            )
            if not cursor.fetchone():
                cursor.execute(
                    """
                    INSERT INTO componentes (id, nome, servidor_id, servidor_empresa_id)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (comp_id, comp_nome, servidor_id, EMPRESA_ID)
                )

        conexao.commit()
        return servidor_id

    except Exception as erro:
        print("Erro ao salvar perfil do servidor:", erro)
        conexao.rollback()
        raise SystemExit(1)

    finally:
        cursor.close()
        conexao.close()


def coletar_dados():
    agora = datetime.now()
    uso_cpu = p.cpu_percent(interval=0.5)
    frequencia = p.cpu_freq(percpu=False)
    frequencia_cpu = frequencia.current if frequencia else None
    status_cpu = discretizar_cpu(uso_cpu)

    memoria = p.virtual_memory()
    memoria_total = memoria.total / (1024 ** 3)
    memoria_disponivel = memoria.available / (1024 ** 3)
    uso_memoria = memoria.percent
    status_memoria = discretizar_memoria(uso_memoria)

    caminho_disco = os.environ.get("SystemDrive", "C:") + "\\" if os.name == "nt" else "/"
    disco = p.disk_usage(caminho_disco)
    status_disco = discretizar_disco(disco.percent)

    return {
        "momento": agora,
        "uso_cpu": uso_cpu,
        "status_cpu": status_cpu,
        "tempo_cpu": controle_tempo["cpu_tempo_seg"],
        "frequencia_cpu": frequencia_cpu,
        "memoria_total": memoria_total,
        "memoria_disponivel": memoria_disponivel,
        "uso_memoria": uso_memoria,
        "status_memoria": status_memoria,
        "tempo_memoria": controle_tempo["memoria_tempo_seg"],
        "uso_disco": disco.percent,
        "status_disco": status_disco,
        "tempo_disco": controle_tempo["disco_tempo_seg"]
    }


def salvar_captura(servidor_id, dados):
    conexao = conectar()
    cursor = conexao.cursor()

    try:
        sql = """
            INSERT INTO captura (
                tipo,
                valor,
                unidade_medida,
                componentes_id,
                componentes_servidor_id,
                componentes_servidor_empresa_id
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """

        cursor.execute(sql, ("Uso CPU", dados["uso_cpu"], "%", 1, servidor_id, EMPRESA_ID))

        cursor.execute(sql, ("Uso Memoria", dados["uso_memoria"], "%", 2, servidor_id, EMPRESA_ID))

        cursor.execute(sql, ("Uso Disco", dados["uso_disco"], "%", 3, servidor_id, EMPRESA_ID))

        conexao.commit()

    except Exception as erro:
        print("Erro ao salvar captura:", erro)
        conexao.rollback()

    finally:
        cursor.close()
        conexao.close()


def limpar():
    os.system("cls" if os.name == "nt" else "clear")


def voltar():
    print()
    input("| Pressione ENTER para voltar ao menu...")
    limpar()


def exibir_menu():
    momento = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    print("""
+--------------------------------------------+-----------------------------------------+
|                    MENU DE CONSULTA DE RECURSOS                                      |
+--------------------------------------------+-----------------------------------------+
| Data e hora atual: {:<65} |
+--------------------------------------------+-----------------------------------------+
| 1. Menu de opções sobre a CPU                                                        |
| 2. Menu de memória RAM                                                               |
| 3. Menu de disco principal                                                           |
| 4. Captura completa                                                                  |
| 5. Informações da máquina                                                            |
| 6. Consultar dados armazenados                                                       |
|                                                                                      |
| Digite 'sair' para sair.                                                             |
+--------------------------------------------+-----------------------------------------+
""".format(momento))


def menu_cpu(servidor_id):
    while True:
        limpar()

        print("""
+--------------------------------------------+-----------------------------------------+
|                                  MENU CPU                                            |
+--------------------------------------------+-----------------------------------------+
| 1.1 Consultar o uso da CPU                                                           |
| 1.2 Consultar núcleos lógicos e físicos                                              |
| 1.3 Consultar frequência da CPU                                                      |
|                                                                                      |
| Digite 'voltar' para retornar.                                                       |
+--------------------------------------------+-----------------------------------------+
""")

        opcao = input("| Digite a opção desejada: ").strip().lower()

        if opcao == "1.1":
            limpar()
            dados = coletar_dados()
            salvar_captura(servidor_id, dados)
            momento = dados["momento"].strftime("%d/%m/%Y %H:%M:%S")

            alerta = "SISTEMA NORMAL"
            if dados['status_cpu'] != "NORMAL":
                alerta = "Atenção! CPU em status " + dados['status_cpu']

            print("""
+--------------------------------------------+-----------------------------------------+
|                                USO DA CPU                                            |
+--------------------------------------------+-----------------------------------------+
| Momento da captura: {:<64} |
| Uso da CPU: {:<72} |
| Status da CPU: {:<69} |
| Situação: {:<74} |
|                                                                                      |
| Captura salva no banco de dados.                                                     |
+--------------------------------------------+-----------------------------------------+
""".format(momento, f"{dados['uso_cpu']:.2f}%", dados['status_cpu'], alerta))
            
            voltar()

        elif opcao == "1.2":
            limpar()
            dados = coletar_dados()
            salvar_captura(servidor_id, dados)
            momento = dados["momento"].strftime("%d/%m/%Y %H:%M:%S")

            print("""
+--------------------------------------------+-----------------------------------------+
|                              NÚCLEOS DA CPU                                          |
+--------------------------------------------+-----------------------------------------+
| Momento da captura: {:<64} |
| Total de núcleos lógicos: {:<58} |
| Total de núcleos físicos: {:<58} |
|                                                                                      |
| Captura salva no banco de dados.                                                     |
+--------------------------------------------+-----------------------------------------+
""".format(momento, p.cpu_count(logical=True), p.cpu_count(logical=False)))

            voltar()

        elif opcao == "1.3":
            limpar()
            dados = coletar_dados()
            salvar_captura(servidor_id, dados)
            momento = dados["momento"].strftime("%d/%m/%Y %H:%M:%S")

            freq_txt = f"{dados['frequencia_cpu']:.2f} MHz" if dados["frequencia_cpu"] is not None else "Frequência da CPU indisponível."

            print("""
+--------------------------------------------+-----------------------------------------+
|                            FREQUÊNCIA DA CPU                                         |
+--------------------------------------------+-----------------------------------------+
| Momento da captura: {:<64} |
| Frequência da CPU: {:<65} |
|                                                                                      |
| Captura salva no banco de dados.                                                     |
+--------------------------------------------+-----------------------------------------+
""".format(momento, freq_txt))

            voltar()

        elif opcao in ["voltar", "v"]:
            limpar()
            break

        else:
            print("+--------------------------------------------+-----------------------------------------+")
            print("| Opção inválida.                                                                      |")
            print("+--------------------------------------------+-----------------------------------------+")
            time.sleep(1.5)


def menu_memoria(servidor_id):
    while True:
        limpar()

        print("""
+--------------------------------------------+-----------------------------------------+
|                            MENU MEMÓRIA RAM                                          |
+--------------------------------------------+-----------------------------------------+
| 2.1 Consultar o total de memória instalada                                           |
| 2.2 Consultar a memória disponível                                                   |
| 2.3 Consultar percentual de uso da memória                                           |
|                                                                                      |
| Digite 'voltar' para retornar.                                                       |
+--------------------------------------------+-----------------------------------------+
""")

        opcao = input("| Digite a opção desejada: ").strip().lower()

        if opcao == "2.1":
            limpar()
            dados = coletar_dados()
            salvar_captura(servidor_id, dados)
            momento = dados["momento"].strftime("%d/%m/%Y %H:%M:%S")

            print("""
+--------------------------------------------+-----------------------------------------+
|                              MEMÓRIA TOTAL                                           |
+--------------------------------------------+-----------------------------------------+
| Momento da captura: {:<64} |
| Total de memória instalada: {:<56} |
|                                                                                      |
| Captura salva no banco de dados.                                                     |
+--------------------------------------------+-----------------------------------------+
""".format(momento, f"{dados['memoria_total']:.2f} GB"))

            voltar()

        elif opcao == "2.2":
            limpar()
            dados = coletar_dados()
            salvar_captura(servidor_id, dados)
            momento = dados["momento"].strftime("%d/%m/%Y %H:%M:%S")

            print("""
+--------------------------------------------+-----------------------------------------+
|                            MEMÓRIA DISPONÍVEL                                        |
+--------------------------------------------+-----------------------------------------+
| Momento da captura: {:<64} |
| Memória disponível agora: {:<58} |
|                                                                                      |
| Captura salva no banco de dados.                                                     |
+--------------------------------------------+-----------------------------------------+
""".format(momento, f"{dados['memoria_disponivel']:.2f} GB"))

            voltar()

        elif opcao == "2.3":
            limpar()
            dados = coletar_dados()
            salvar_captura(servidor_id, dados)
            momento = dados["momento"].strftime("%d/%m/%Y %H:%M:%S")

            alerta = "SISTEMA NORMAL"
            if dados['status_memoria'] != "NORMAL":
                alerta = "Atenção! Memória em status " + dados['status_memoria']

            print("""
+--------------------------------------------+-----------------------------------------+
|                             USO DA MEMÓRIA                                           |
+--------------------------------------------+-----------------------------------------+
| Momento da captura: {:<64} |
| Percentual de uso da memória: {:<54} |
| Status da Memória: {:<65} |
| Situação: {:<74} |
|                                                                                      |
| Captura salva no banco de dados.                                                     |
+--------------------------------------------+-----------------------------------------+
""".format(momento, f"{dados['uso_memoria']:.2f}%", dados['status_memoria'], alerta))

            voltar()

        elif opcao in ["voltar", "v"]:
            limpar()
            break

        else:
            print("+--------------------------------------------+-----------------------------------------+")
            print("| Opção inválida.                                                                      |")
            print("+--------------------------------------------+-----------------------------------------+")
            time.sleep(1.5)


def menu_disco(servidor_id):
    while True:
        limpar()

        print("""
+--------------------------------------------+-----------------------------------------+
|                                MENU DISCO                                            |
+--------------------------------------------+-----------------------------------------+
| 3.1 Consultar percentual de uso do disco principal                                   |
|                                                                                      |
| Digite 'voltar' para retornar.                                                       |
+--------------------------------------------+-----------------------------------------+
""")

        opcao = input("| Digite a opção desejada: ").strip().lower()

        if opcao == "3.1":
            limpar()
            dados = coletar_dados()
            salvar_captura(servidor_id, dados)
            momento = dados["momento"].strftime("%d/%m/%Y %H:%M:%S")

            alerta = "SISTEMA NORMAL"
            if dados['status_disco'] != "NORMAL":
                alerta = "Atenção! Disco em status " + dados['status_disco']

            print("""
+--------------------------------------------+-----------------------------------------+
|                              USO DO DISCO                                            |
+--------------------------------------------+-----------------------------------------+
| Momento da captura: {:<64} |
| Uso do disco principal: {:<60} |
| Status do Disco: {:<67} |
| Situação: {:<74} |
|                                                                                      |
| Captura salva no banco de dados.                                                     |
+--------------------------------------------+-----------------------------------------+
""".format(momento, f"{dados['uso_disco']:.2f}%", dados['status_disco'], alerta))

            voltar()

        elif opcao in ["voltar", "v"]:
            limpar()
            break

        else:
            print("+--------------------------------------------+-----------------------------------------+")
            print("| Opção inválida.                                                                      |")
            print("+--------------------------------------------+-----------------------------------------+")
            time.sleep(1.5)


def captura_completa(servidor_id):
    limpar()

    print("+--------------------------------------------+-----------------------------------------+")
    print("| Realizando captura...                                                                |")
    print("+--------------------------------------------+-----------------------------------------+")
    print()

    dados = coletar_dados()
    salvar_captura(servidor_id, dados)
    momento = dados["momento"].strftime("%d/%m/%Y %H:%M:%S")

    freq_txt = f"{dados['frequencia_cpu']:.2f} MHz" if dados["frequencia_cpu"] is not None else "indisponível"

    print("""
+--------------------------------------------+-----------------------------------------+
|                            CAPTURA COMPLETA                                          |
+--------------------------------------------+-----------------------------------------+
| Momento da captura: {:<64} |
|                                                                                      |
| Uso da CPU: {:<72} |
| Frequência da CPU: {:<65} |
| Memória total: {:<69} |
| Memória disponível: {:<64} |
| Uso da memória: {:<68} |
| Uso do disco principal: {:<60} |
|                                                                                      |
| Captura salva com sucesso no banco de dados.                                         |
+--------------------------------------------+-----------------------------------------+
""".format(
        momento,
        f"{dados['uso_cpu']:.2f}%",
        freq_txt,
        f"{dados['memoria_total']:.2f} GB",
        f"{dados['memoria_disponivel']:.2f} GB",
        f"{dados['uso_memoria']:.2f}%",
        f"{dados['uso_disco']:.2f}%"
    ))

    voltar()


def exibir_perfil():
    limpar()

    memoria_total = p.virtual_memory().total / (1024 ** 3)

    print("""
+--------------------------------------------+-----------------------------------------+
|                        INFORMAÇÕES DA MÁQUINA                                        |
+--------------------------------------------+-----------------------------------------+
| Nome da máquina: {:<67} |
| Sistema operacional: {:<63} |
| Versão do sistema: {:<65} |
| Núcleos físicos: {:<67} |
| Núcleos lógicos: {:<67} |
| Memória total: {:<69} |
+--------------------------------------------+-----------------------------------------+
""".format(
        socket.gethostname(),
        platform.system(),
        platform.release(),
        p.cpu_count(logical=False),
        p.cpu_count(logical=True),
        f"{memoria_total:.2f} GB"
    ))

    voltar()

def exibir_banco():
    limpar()

    print("""
    +--------------------------------------------+-----------------------------------------+
    |                      Informações armazenadas no banco de dados                       |
    +--------------------------------------------+-----------------------------------------+
    """)

    conexao = conectar()
    cursor = conexao.cursor()
    
    cursor.execute("SELECT * FROM captura")
    relatorio = cursor.fetchall()

    print(tabulate(
        relatorio,
        headers=["Tipo", "Valor", "Unidade de medida", "ID componente", "ID Servidor", "ID empresa"],
        tablefmt="grid"
    ))

    voltar()


def iniciar_captura(servidor_id):
    while True:
        dados = coletar_dados()
        salvar_captura(servidor_id, dados)
        time.sleep(10)


def main():
    limpar()

    print("+--------------------------------------------+-----------------------------------------+")
    print("| Iniciando sistema de monitoramento...                                                |")
    print("| Conectando ao banco de dados...                                                      |")
    print("+--------------------------------------------+-----------------------------------------+")

    servidor_id = salvar_perfil()

    print("+--------------------------------------------+-----------------------------------------+")
    print(f"| ID do servidor: {servidor_id:<68} |")
    print("+--------------------------------------------+-----------------------------------------+")

    thread_coleta = threading.Thread(target=iniciar_captura, args=(servidor_id,), daemon=True)
    thread_coleta.start()

    time.sleep(2)
    limpar()

    while True:
        exibir_menu()

        opcao = input("| Digite a opção desejada: ").strip().lower()

        if opcao == "1":
            menu_cpu(servidor_id)
        elif opcao == "2":
            menu_memoria(servidor_id)
        elif opcao == "3":
            menu_disco(servidor_id)
        elif opcao == "4":
            captura_completa(servidor_id)
        elif opcao == "5":
            exibir_perfil()
        elif opcao == "6":
            exibir_banco()
        elif opcao in ["sair", "exit", "quit", "q"]:
            limpar()
            print("+--------------------------------------------+-----------------------------------------+")
            print("| Encerrando sistema de monitoramento...                                               |")
            print("+--------------------------------------------+-----------------------------------------+")
            time.sleep(1)
            print("+--------------------------------------------+-----------------------------------------+")
            print("| Programa encerrado.                                                                  |")
            print("+--------------------------------------------+-----------------------------------------+")
            break
        else:
            print("+--------------------------------------------+-----------------------------------------+")
            print("| Opção inválida.                                                                      |")
            print("+--------------------------------------------+-----------------------------------------+")
            time.sleep(1.5)
            limpar()


main()