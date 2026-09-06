import os
import socket
import platform
import psutil as p
import time
from datetime import datetime
import mysql.connector as mysql
from dotenv import load_dotenv

load_dotenv()

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
    
    if uso_cpu < 1.5:
        controle_tempo["cpu_inicio_critico"] = None
        controle_tempo["cpu_tempo_seg"] = 0
        return "NORMAL"
        
    elif uso_cpu < 5:
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
    
    if uso_memoria < 1.5:
        controle_tempo["memoria_inicio_critico"] = None
        controle_tempo["memoria_tempo_seg"] = 0
        return "NORMAL"
        
    elif uso_memoria < 5:
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
    
    if uso_disco < 1.5:
        controle_tempo["disco_inicio_critico"] = None
        controle_tempo["disco_tempo_seg"] = 0
        return "NORMAL"
        
    elif uso_disco < 5:
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
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
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
        versao_so = platform.release()
        memoria = p.virtual_memory()
        memoria_total = memoria.total / (1024 ** 3)
        nucleos_fisicos = p.cpu_count(logical=False)
        nucleos_logicos = p.cpu_count(logical=True)

        cursor.execute(
            "SELECT id FROM maquinas WHERE nome = %s",
            (nome_maquina,)
        )
        resultado = cursor.fetchone()

        if resultado:
            maquina_id = resultado[0]

            atualizar = """
                UPDATE maquinas SET
                    sistema_operacional = %s,
                    versao_sistema_operacional = %s,
                    nucleos_fisicos = %s,
                    nucleos_logicos = %s,
                    memoria_total_gb = %s
                WHERE id = %s

            """
            print("Máquina atualizada com sucesso.")

            valores = (
                nome_so,
                versao_so,
                nucleos_fisicos,
                nucleos_logicos,
                memoria_total,
                maquina_id
            )

            cursor.execute(atualizar, valores)
        else:
            inserir = """
                INSERT INTO maquinas (
                    nome,
                    sistema_operacional,
                    versao_sistema_operacional,
                    nucleos_fisicos,
                    nucleos_logicos,
                    memoria_total_gb
                )
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            print("Máquina registrada com sucesso.")

            valores = (
                nome_maquina,
                nome_so,
                versao_so,
                nucleos_fisicos,
                nucleos_logicos,
                memoria_total
            )

            cursor.execute(inserir, valores)
            maquina_id = cursor.lastrowid

        conexao.commit()
        return maquina_id

    except Exception as erro:
        print("Erro ao salvar perfil da máquina:", erro)
        conexao.rollback()
        raise SystemExit(1)

    finally:
        cursor.close()
        conexao.close()

def coletar_dados():
    agora = datetime.now()
    uso_cpu = p.cpu_percent(interval=0.5)
    status_cpu = discretizar_cpu(uso_cpu)
    frequencia = p.cpu_freq(percpu=False)
    frequencia_cpu = frequencia.current if frequencia else None

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

def salvar_captura(maquina_id, dados):
    conexao = conectar()
    cursor = conexao.cursor()

    try:
        inserir_captura = """
            INSERT INTO capturas (
                maquina_id,
                uso_cpu_percentual, 
                status_cpu,
                tempo_seg_cpu,
                frequencia_cpu_mhz,
                memoria_disponivel_gb,
                uso_memoria_percentual,
                status_memoria,
                tempo_seg_memoria,
                uso_disco_percentual,
                status_disco,
                tempo_seg_disco,
                criado_em
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
            # VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)

        valores = (
            maquina_id,
            dados["uso_cpu"],
            dados["status_cpu"],
            dados["tempo_cpu"],
            dados["frequencia_cpu"],
            dados["memoria_disponivel"],
            dados["uso_memoria"],
            dados["status_memoria"],
            dados["tempo_memoria"],
            dados["uso_disco"],
            dados["status_disco"],
            dados["tempo_disco"],
            dados["momento"]
        )

        cursor.execute(inserir_captura, valores)
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
    input("Pressione ENTER para voltar ao menu...")
    limpar()

def exibir_menu():
    momento = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    print("-" * 55)
    print("MENU DE CONSULTA DE RECURSOS")
    print()
    print(f"Data e hora atual: {momento}")
    print()
    print("1. Menu de opções sobre a CPU")
    print("2. Menu de memória RAM")
    print("3. Menu de disco principal")
    print("4. Captura completa")
    print("5. Informações da máquina")
    print()
    print("Digite 'sair' para sair.")
    print("-" * 55)

def menu_cpu(maquina_id):
    while True:
        limpar()

        print("-" * 50)
        print("MENU CPU")
        print()
        print("1.1 Consultar o uso da CPU")
        print("1.2 Consultar núcleos lógicos e físicos")
        print("1.3 Consultar frequência da CPU")
        print()
        print("Digite 'voltar' para retornar.")
        print("-" * 50)

        opcao = input("Digite a opção desejada: ").strip().lower()

        if opcao == "1.1":
            limpar()
            dados = coletar_dados()
            salvar_captura(maquina_id, dados)
            momento = dados["momento"].strftime("%d/%m/%Y %H:%M:%S")

            print("-" * 50)
            print("USO DA CPU")
            print()
            print(f"Momento da captura: {momento}")
            print(f"Uso da CPU: {dados['uso_cpu']:.2f}%")
            print()
            print("Captura salva no banco de dados.")
            print("-" * 50)

            voltar()

        elif opcao == "1.2":
            limpar()
            dados = coletar_dados()
            salvar_captura(maquina_id, dados)
            momento = dados["momento"].strftime("%d/%m/%Y %H:%M:%S")

            print("-" * 50)
            print("NÚCLEOS DA CPU")
            print()
            print(f"Momento da captura: {momento}")
            print(f"Total de núcleos lógicos: {p.cpu_count(logical=True)}")
            print(f"Total de núcleos físicos: {p.cpu_count(logical=False)}")
            print()
            print("Captura salva no banco de dados.")
            print("-" * 50)

            voltar()

        elif opcao == "1.3":
            limpar()
            dados = coletar_dados()
            salvar_captura(maquina_id, dados)
            momento = dados["momento"].strftime("%d/%m/%Y %H:%M:%S")

            print("-" * 50)
            print("FREQUÊNCIA DA CPU")
            print()
            print(f"Momento da captura: {momento}")

            if dados["frequencia_cpu"] is not None:
                print(f"Frequência da CPU: {dados['frequencia_cpu']:.2f} MHz")
            else:
                print("Frequência da CPU indisponível.")

            print()
            print("Captura salva no banco de dados.")
            print("-" * 50)

            voltar()

        elif opcao in ["voltar", "v"]:
            limpar()
            break

        else:
            print("Opção inválida.")
            time.sleep(1.5)

def menu_memoria(maquina_id):
    while True:
        limpar()

        print("-" * 50)
        print("MENU MEMÓRIA RAM")
        print()
        print("2.1 Consultar o total de memória instalada")
        print("2.2 Consultar a memória disponível")
        print("2.3 Consultar percentual de uso da memória")
        print()
        print("Digite 'voltar' para retornar.")
        print("-" * 50)

        opcao = input("Digite a opção desejada: ").strip().lower()

        if opcao == "2.1":
            limpar()
            dados = coletar_dados()
            salvar_captura(maquina_id, dados)
            momento = dados["momento"].strftime("%d/%m/%Y %H:%M:%S")

            print("-" * 50)
            print("MEMÓRIA TOTAL")
            print()
            print(f"Momento da captura: {momento}")
            print(f"Total de memória instalada: {dados['memoria_total']:.2f} GB")
            print()
            print("Captura salva no banco de dados.")
            print("-" * 50)

            voltar()

        elif opcao == "2.2":
            limpar()
            dados = coletar_dados()
            salvar_captura(maquina_id, dados)

            momento = dados["momento"].strftime("%d/%m/%Y %H:%M:%S")

            print("-" * 50)
            print("MEMÓRIA DISPONÍVEL")
            print()
            print(f"Momento da captura: {momento}")
            print(f"Memória disponível agora: {dados['memoria_disponivel']:.2f} GB")
            print()
            print("Captura salva no banco de dados.")
            print("-" * 50)

            voltar()

        elif opcao == "2.3":
            limpar()
            dados = coletar_dados()
            salvar_captura(maquina_id, dados)
            momento = dados["momento"].strftime("%d/%m/%Y %H:%M:%S")

            print("-" * 50)
            print("USO DA MEMÓRIA")
            print()
            print(f"Momento da captura: {momento}")
            print(f"Percentual de uso da memória: {dados['uso_memoria']:.2f}%")
            print()
            print("Captura salva no banco de dados.")
            print("-" * 50)

            voltar()

        elif opcao in ["voltar", "v"]:
            limpar()
            break

        else:
            print("Opção inválida.")
            time.sleep(1.5)

def menu_disco(maquina_id):
    while True:
        limpar()

        print("-" * 50)
        print("MENU DISCO")
        print()
        print("3.1 Consultar percentual de uso do disco principal")
        print()
        print("Digite 'voltar' para retornar.")
        print("-" * 50)

        opcao = input("Digite a opção desejada: ").strip().lower()

        if opcao == "3.1":
            limpar()
            dados = coletar_dados()
            salvar_captura(maquina_id, dados)
            momento = dados["momento"].strftime("%d/%m/%Y %H:%M:%S")

            print("-" * 50)
            print("USO DO DISCO")
            print()
            print(f"Momento da captura: {momento}")
            print(f"Uso do disco principal: {dados['uso_disco']:.2f}%")
            print()
            print("Captura salva no banco de dados.")
            print("-" * 50)

            voltar()

        elif opcao in ["voltar", "v"]:
            limpar()
            break

        else:
            print("Opção inválida.")
            time.sleep(1.5)

def captura_completa(maquina_id):
    limpar()

    print("Realizando captura...")
    print()

    dados = coletar_dados()
    salvar_captura(maquina_id, dados)
    momento = dados["momento"].strftime("%d/%m/%Y %H:%M:%S")

    print("-" * 55)
    print("CAPTURA COMPLETA")
    print()
    print(f"Momento da captura: {momento}")
    print()
    print(f"Uso da CPU: {dados['uso_cpu']:.2f}%")

    if dados["frequencia_cpu"] is not None:
        print(f"Frequência da CPU: {dados['frequencia_cpu']:.2f} MHz")
    else:
        print("Frequência da CPU: indisponível")

    print(f"Memória total: {dados['memoria_total']:.2f} GB")
    print(f"Memória disponível: {dados['memoria_disponivel']:.2f} GB")
    print(f"Uso da memória: {dados['uso_memoria']:.2f}%")
    print(f"Uso do disco principal: {dados['uso_disco']:.2f}%")
    print()
    print("Captura salva com sucesso no banco de dados.")
    print("-" * 55)

    voltar()

def exibir_perfil():
    limpar()

    memoria_total = p.virtual_memory().total / (1024 ** 3)

    print("-" * 55)
    print("INFORMAÇÕES DA MÁQUINA")
    print()
    print(f"Nome da máquina: {socket.gethostname()}")
    print(f"Sistema operacional: {platform.system()}")
    print(f"Versão do sistema: {platform.release()}")
    print(f"Núcleos físicos: {p.cpu_count(logical=False)}")
    print(f"Núcleos lógicos: {p.cpu_count(logical=True)}")
    print(f"Memória total: {memoria_total:.2f} GB")
    print("-" * 55)

    voltar()

def main():
    limpar()

    print("Iniciando sistema de monitoramento...")
    print("Conectando ao banco de dados...")

    maquina_id = salvar_perfil()

    print(f"ID da máquina: {maquina_id}")

    time.sleep(2)
    limpar()

    while True:
        exibir_menu()

        opcao = input("Digite a opção desejada: ").strip().lower()

        if opcao == "1":
            menu_cpu(maquina_id)
        elif opcao == "2":
            menu_memoria(maquina_id)
        elif opcao == "3":
            menu_disco(maquina_id)
        elif opcao == "4":
            captura_completa(maquina_id)
        elif opcao == "5":
            exibir_perfil()
        elif opcao in ["sair", "exit", "quit", "q"]:
            limpar()
            print("Encerrando sistema de monitoramento...")
            time.sleep(1)
            print("Programa encerrado.")
            break
        else:
            print("Opção inválida.")
            time.sleep(1.5)
            limpar()

# def iniciar_captura(maquina_id):
#     i = 1 
#     while True:
          
#         dados = coletar_dados()
#         salvar_captura(maquina_id, dados)
#         print("Captura" , i, "Pressione control + c para sair")
#         time.sleep(10)
#         i = i + 1
    
# iniciar_captura(1)
main()


