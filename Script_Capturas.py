from datetime import datetime
import os
import mysql.connector as m
import psutil as p
from dotenv import load_dotenv

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


def main():
  print(
      "Iniciando monitoramento contínuo (capturas a cada 1 minuto). Pressione"
      " Ctrl+C para parar."
  )
  contador = 1

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

      contador += 1

    except KeyboardInterrupt:
      print("\nMonitoramento encerrado pelo usuário.")
      break
    except Exception as e:
      print("Erro inesperado no loop:", e)


if __name__ == "__main__":
  main()