
# Sistema de Monitoramento de Servidores
Aplicação em Python para monitoramento de recursos do sistema (CPU, Memória RAM e Disco) com interface via terminal, coleta automatizada em segundo plano e inserção no banco de dados MySQL.

---

## Funcionalidades
Registro automático do servidor: Identifica hostname, IP, sistema operacional e registra no banco de dados.

Coleta automática: Captura as métricas a cada 10 segundos automaticamente em segundo plano.

Discretização dos componentes: Transformamos os dados capturados em categorias de níveis de alerta.

Menu via linha de comando (terminal):

- Consulta detalhada de CPU (uso %, núcleos lógicos/físicos, frequência).

- Consulta de Memória RAM (total, disponível, uso %).

- Consulta de Disco principal.

- Relatório de captura completa e perfil do hardware.

---

## Tecnologias utilizadas
**Linguagem:** 
  * Python

**Bibliotecas Principais (Dependências):**
  * `psutil`: Coleta de métricas do sistema e do hardware (CPU, memória e disco).
  * `mysql-connector-python`: Conexão e execução de comandos no banco de dados MySQL.
  * `python-dotenv`: Gerenciamento de variáveis de ambiente para dados sensíveis.

**Módulos Nativos do Python:**
  * `threading`: Executa os processos e coleta continuamente em segundo plano.
  * `os` / `platform` / `socket`: Captura de informações do sistema operacional, hostname e IP.
  * `time` / `datetime`: Manipulação de datas, horários e intervalos de tempo.

**Banco de Dados:**
  * MySQL

---

## Instalação e configuração
1. Clonar ou baixar o projeto

2. Instalar dependências

Execute o comando abaixo no terminal para instalar as bibliotecas necessárias:
`pip install psutil mysql-connector-python python-dotenv`

3. Configurar Variáveis de Ambiente

Crie um arquivo .env na mesma pasta do script para configurar a conexão com o banco de dados MySQL e cole o código abaixo:

```
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=sua_senha
DB_NAME=grupo_07
```

---

## Estrutura do Banco de Dados
Certifique-se de que o banco de dados grupo_07 contenha as tabelas abaixo antes de rodar o programa:

```
servidor (id, ip, hostname, sistema_operacional, empresa_id)

componentes (id, nome, servidor_id, servidor_empresa_id)

captura (tipo, valor, unidade_medida, componentes_id, componentes_servidor_id, componentes_servidor_empresa_id)
```
---

## Licença

Este projeto é de uso exclusivamente educacional e acadêmico.


