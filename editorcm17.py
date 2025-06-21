from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash
from werkzeug.utils import secure_filename
import os
import uuid

app = Flask(__name__)
app.secret_key = 'chave-secreta'
app.config['UPLOAD_FOLDER'] = 'uploads'  # pasta onde vai salvar arquivos enviados

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

OFFSET_INICIAL = 0x2153A0E
OFFSET_FINAL = 0x246767E
TAMANHO_JOGADOR = 136
NOME_LEN = 16
SOBRENOME_LEN = 20

ARQUIVO_IDADES = "dados/idades.txt"

# ----------------------------
# Funções de carga
# ----------------------------
def carregar_idades_do_arquivo(caminho_arquivo=ARQUIVO_IDADES):
    idades = {}
    with open(caminho_arquivo, "r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith("#"):
                continue
            idade_str, faixa = linha.split(":")
            inicio_hex, fim_hex = faixa.strip().split("-")
            inicio = int(inicio_hex, 16)
            fim = int(fim_hex, 16)
            idades[idade_str.strip()] = (inicio, fim)
    return idades

def get_arquivo_usuario():
    return session.get("arquivo_usuario", "packres-android_core.png")

def carregar_atributos(caminho):
    atributos = {}
    with open(caminho, "r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith("#"):
                continue
            nome, cod = linha.split("=")
            atributos[nome.strip()] = int(cod.strip(), 16)
    return atributos

nacionalidade2_dict = {}

def carregar_nacionalidade2_dict(caminho="dados/nacionalidade2.txt"):
    d = {}
    with open(caminho, "r", encoding="utf-8") as f:
        for linha in f:
            if '/' in linha:
                nome, cod = linha.strip().split("/")
                cod = cod.strip().replace(" ", "")
                if len(cod) == 6:
                    d[nome.strip()] = cod.upper()
    return d

nacionalidade2_dict = carregar_nacionalidade2_dict()

def extrair_nacionalidade_nome(b41, b42, b43, nacionalidade_dict):
    b41 = 0x88
    parte_alta_42 = (b42 & 0xF0) >> 4
    b42_final = (parte_alta_42 << 4) | 0x0E

    parte_alta_43 = (b43 & 0xF0) >> 4
    if parte_alta_43 in (0x0, 0xC, 0x8): grupo_final = 0
    elif parte_alta_43 in (0x1, 0xD, 0x9): grupo_final = 1
    elif parte_alta_43 in (0x2, 0xE, 0xA): grupo_final = 2
    elif parte_alta_43 in (0x3, 0xF, 0xB): grupo_final = 3
    else: return "Desconhecido"

    b43_final = (grupo_final << 4) | (b43 & 0x0F)
    codigo_hex = f"{b41:02X}{b42_final:02X}{b43_final:02X}"

    for nome, valor in nacionalidade_dict.items():
        if valor.replace(" ", "").upper() == codigo_hex:
            return nome
    return "Desconhecido"

passe_dict = carregar_atributos("dados/passe.txt")
finalizacoes_dict = carregar_atributos("dados/finalizacoes.txt")
cruzamentos_dict = carregar_atributos("dados/cruzamentos.txt")
tiroslongos_dict = carregar_atributos("dados/tiroslongos.txt")
drible_dict = carregar_atributos("dados/drible.txt")
recepcao_dict = carregar_atributos("dados/recepcao.txt")

# Pênaltis/Faltas (1 byte, Info 1)
penaltis_dict = {
    "☆☆☆/☆☆☆": 0x00,
    "★☆☆/☆☆☆": 0x10,
    "★★☆/☆☆☆": 0x20,
    "★★★/☆☆☆": 0x30,
    "☆☆☆/★☆☆": 0x40,
    "★☆☆/★☆☆": 0x50,
    "★★☆/★☆☆": 0x60,
    "★★★/★☆☆": 0x70,
    "☆☆☆/★★☆": 0x80,
    "★☆☆/★★☆": 0x90,
    "★★☆/★★☆": 0xA0,
    "★★★/★★☆": 0xB0,
    "☆☆☆/★★★": 0xC0,
    "★☆☆/★★★": 0xD0,
    "★★☆/★★★": 0xE0,
    "★★★/★★★": 0xF0,
}

# Inverso para leitura
valor_para_penaltis = {v: k for k, v in penaltis_dict.items()}

# Habilidade "Escanteios"
habilidade_escanteios = {
    "☆☆☆": 0x08,
    "★☆☆": 0x1B,
    "★★☆": 0x68,
    "★★★": 0x38,
}

escanteios_dict = habilidade_escanteios

valor_para_escanteios = {v: k for k, v in habilidade_escanteios.items()}

idades_dict = carregar_idades_do_arquivo()

posicoes2_dict = {
    "VAZIO": 0x00,
    "MAE": 0x60,
    "(MAE)": 0x40
}

grupos_43 = {
    (0x0, 0xC, 0x8): ["VAZIO", "MAD", "(MAD)"], 
    (0x1, 0xD, 0x9): ["VAZIO", "MAD", "(MAD)"], 
    (0x2, 0xE, 0xA): ["VAZIO", "MAD", "(MAD)"], 
    (0x3, 0xF, 0xB): ["VAZIO", "MAD", "(MAD)"]
}

posicao3_map = {}

for grupo, nomes in grupos_43.items():
    for nibble, nome in zip(grupo, nomes):
        posicao3_map[nome] = nibble

grupo_63 = {
    (0x19, 0x59, 0x79): ["VAZIO", "(AT)", "AT"]
}

posicao3_opcoes = sorted(set(sum(grupos_43.values(), [])))
posicao4_opcoes = sorted(set(sum(grupo_63.values(), [])))

def valor_hex_para_idade(valor):
    for idade, (inicio, fim) in idades_dict.items():
        if fim <= valor <= inicio:
            return idade
    return ""

def carregar_times(caminho="dados/times.txt"):
    times = {}
    with open(caminho, "r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith("#"):
                continue
            cod, nome = linha.split(":")
            cod_bytes = bytes.fromhex(cod.strip())
            times[cod_bytes] = nome.strip()
    return times

times_dict = carregar_times()

def carregar_posicoes_arquivo(caminho_arquivo="dados/posição1.txt"):
    posicoes = {}
    with open(caminho_arquivo, "r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith("#"):
                continue
            nome, hexstr = linha.split("/")
            hex1, hex2 = hexstr.strip().split()
            posicoes[nome.strip()] = (int(hex1, 16), int(hex2, 16))
    return posicoes

posicoes1_dict = carregar_posicoes_arquivo()

def carregar_movimento_dict(caminho="dados/movimento.txt"):
    movimento_dict = {}
    with open(caminho, "r", encoding="utf-8") as f:
        for linha in f:
            if '=' in linha:
                chave, valor = linha.strip().split("=")
                movimento_dict[chave] = int(valor, 16)
    return movimento_dict

movimento_dict = carregar_movimento_dict()

def carregar_forca_dict(caminho="dados/forca.txt"):
    forca_dict = {}
    with open(caminho, "r", encoding="utf-8") as f:
        for linha in f:
            if '=' in linha:
                chave, valor = linha.strip().split("=")
                forca_dict[chave] = int(valor, 16)
    return forca_dict

forca_dict = carregar_forca_dict()

def carregar_ritmo_dict(caminho="dados/ritmo.txt"):
    ritmo_dict = {}
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            for linha in f:
                if not linha.strip() or linha.startswith("#"):
                    continue
                try:
                    nome, cod = linha.strip().split("/")
                    cod = cod.strip()
                    if len(cod) != 4:
                        raise ValueError(f"Código de ritmo deve ter 4 dígitos hexadecimais: {cod}")
                    b = bytes.fromhex(cod)
                    ritmo_dict[nome.strip()] = b
                except Exception as e:
                    print(f"[ERRO] Linha inválida em {caminho}: {linha} -> {e}")
    except FileNotFoundError:
        print(f"[ERRO] Arquivo '{caminho}' não encontrado.")
    return ritmo_dict

ritmo_dict = carregar_ritmo_dict()

def carregar_energia_dict(caminho="dados/energia.txt"):
    energia_dict = {}
    with open(caminho, "r", encoding="utf-8") as f:
        for linha in f:
            if '=' in linha:
                chave, valor = linha.strip().split("=")
                energia_dict[chave] = int(valor, 16)
    return energia_dict

energia_dict = carregar_energia_dict()

def carregar_cabeceio_dict(caminho="dados/cabeceio.txt"):
    cabeceio_dict = {}
    with open(caminho, "r", encoding="utf-8") as f:
        for linha in f:
            if '=' in linha:
                chave, valor = linha.strip().split("=")
                cabeceio_dict[chave] = int(valor, 16)
    return cabeceio_dict

cabeceio_dict = carregar_cabeceio_dict()

def carregar_roubada_dict(caminho="dados/roubada.txt"):
    roubada_dict = {}
    with open(caminho, "r", encoding="utf-8") as f:
        for linha in f:
            if '=' in linha:
                chave, valor = linha.strip().split("=")
                roubada_dict[chave] = int(valor, 16)
    return roubada_dict

roubada_dict = carregar_roubada_dict()

def carregar_marcacao_dict(caminho="dados/marcacao.txt"):
    marcacao_dict = {}
    with open(caminho, "r", encoding="utf-8") as f:
        for linha in f:
            if '=' in linha:
                chave, valor = linha.strip().split("=")
                marcacao_dict[chave] = int(valor, 16)
    return marcacao_dict

marcacao_dict = carregar_marcacao_dict()

def carregar_pos_def_dict(caminho="dados/pos_def.txt"):
    pos_def_dict = {}
    with open(caminho, "r", encoding="utf-8") as f:
        for linha in f:
            if '=' in linha:
                chave, valor = linha.strip().split("=")
                pos_def_dict[chave] = int(valor, 16)
    return pos_def_dict

pos_def_dict = carregar_pos_def_dict()

def carregar_lideranca_dict(caminho="dados/lideranca.txt"):
    lideranca_dict = {}
    with open(caminho, "r", encoding="utf-8") as f:
        for linha in f:
            if '=' in linha:
                chave, valor = linha.strip().split("=")
                lideranca_dict[chave] = int(valor, 16)
    return lideranca_dict

lideranca_dict = carregar_lideranca_dict()

def carregar_criatividade_dict(caminho="dados/criatividade.txt"):
    criatividade_dict = {}
    with open(caminho, "r", encoding="utf-8") as f:
        for linha in f:
            if '=' in linha:
                chave, valor = linha.strip().split("=")
                criatividade_dict[chave] = int(valor, 16)
    return criatividade_dict

criatividade_dict = carregar_criatividade_dict()

# ----------------------------
# Leitura dos jogadores
# ----------------------------
import os

def ler_jogadores():
    jogadores = []
    if not os.path.isfile(get_arquivo_usuario()):
        return jogadores  # Evita erro de arquivo ausente

    with open(get_arquivo_usuario(), "rb") as f:
        f.seek(OFFSET_INICIAL)
        total_bytes = OFFSET_FINAL - OFFSET_INICIAL
        total_jogadores = total_bytes // TAMANHO_JOGADOR

        for i in range(total_jogadores):
            bloco = f.read(TAMANHO_JOGADOR)
            if len(bloco) < TAMANHO_JOGADOR:
                break
            b41, b42, b43 = bloco[41], bloco[42], bloco[43]
            nacionalidade_nome = extrair_nacionalidade_nome(b41, b42, b43, nacionalidade2_dict)

            nome = bloco[0:NOME_LEN].decode("utf-8", errors="ignore").strip('\x00')
            sobrenome = bloco[NOME_LEN:NOME_LEN + SOBRENOME_LEN].decode("utf-8", errors="ignore").strip('\x00')

            valor = ((bloco[42] & 0x0F) << 8) | bloco[41]
            idade = valor_hex_para_idade(valor)

            valor_passe = bloco[121]
            nome_passe = next((k for k, v in passe_dict.items() if v == valor_passe), "")

            valor_finalizacoes = bloco[122]
            nome_finalizacoes = next((k for k, v in finalizacoes_dict.items() if v == valor_finalizacoes), "")

            valor_cruzamentos = bloco[116]
            nome_cruzamentos = next((k for k, v in cruzamentos_dict.items() if v == valor_cruzamentos), "")

            valor_tiroslongos = bloco[124]
            nome_tiroslongos = next((k for k, v in tiroslongos_dict.items() if v == valor_tiroslongos), "")

            valor_drible = bloco[117]
            nome_drible = next((k for k, v in drible_dict.items() if v == valor_drible), "")

            valor_recepcao = bloco[118]
            nome_recepcao = next((k for k, v in recepcao_dict.items() if v == valor_recepcao), "")

            valor_movimento = bloco[125]
            nome_movimento = next((k for k, v in movimento_dict.items() if v == valor_movimento), "")

            valor_forca = bloco[73]
            nome_forca = next((k for k, v in forca_dict.items() if v == valor_forca), "")

            valor_ritmo = bloco[70:72]
            nome_ritmo = next((k for k, v in ritmo_dict.items() if v == valor_ritmo), "")

            valor_energia = bloco[72]
            nome_energia = next((k for k, v in energia_dict.items() if v == valor_energia), "")

            valor_cabeceio = bloco[119]
            nome_cabeceio = next((k for k, v in cabeceio_dict.items() if v == valor_cabeceio), "")

            valor_roubada = bloco[123]
            nome_roubada = next((k for k, v in roubada_dict.items() if v == valor_roubada), "")

            valor_marcacao = bloco[120]
            nome_marcacao = next((k for k, v in marcacao_dict.items() if v == valor_marcacao), "")

            valor_pos_def = bloco[69]
            nome_pos_def = next((k for k, v in pos_def_dict.items() if v == valor_pos_def), "")

            valor_lideranca = bloco[74]
            nome_lideranca = next((k for k, v in lideranca_dict.items() if v == valor_lideranca), "")

            valor_criatividade = bloco[68]
            nome_criatividade = next((k for k, v in criatividade_dict.items() if v == valor_criatividade), "")

            val67 = bloco[67]
            penaltis = valor_para_penaltis.get(val67, "")

            val133 = bloco[133]
            escanteios = valor_para_escanteios.get(val133, "")

            val82 = bloco[82]
            val83 = bloco[83]
            nome_pos1 = "NADA"
            for nome_pos, (h1, h2) in posicoes1_dict.items():
                if (h1, h2) == (val82, val83):
                    nome_pos1 = nome_pos
                    break

            val95 = bloco[95]
            nome_pos2 = "VAZIO"
            for nome_pos, val in posicoes2_dict.items():
                if val95 == val:
                    nome_pos2 = nome_pos
                    break

            val43 = (bloco[43] & 0xF0) >> 4
            nome_posicao3 = "VAZIO"
            for grupo, nomes in grupos_43.items():
                if val43 in grupo:
                    nome_posicao3 = nomes[grupo.index(val43)]
                    break

            val63 = bloco[63]
            nome_pos4 = "VAZIO"
            for grupo, nomes in grupo_63.items():
                if val63 in grupo:
                    nome_pos4 = nomes[grupo.index(val63)]
                    break

            id_invertido = bloco[36:38][::-1].hex().upper()
            id_time = bloco[56:58]
            nome_time = times_dict.get(id_time, f"Sem Time ({id_time.hex().upper()})")

            is_goleiro = bloco[39] == 0x80 and bloco[79] in (0xE0, 0xD0)

            b41 = bloco[41]  # byte fixo (ex: 53)
            b42_real = (bloco[42] & 0xF0) >> 4  # parte alta do byte 42
            b43_val = (bloco[43] & 0xF0) >> 4  # parte alta do byte 43

            if b43_val in (0x0, 0xC, 0x8):
                b43_real = 0
            elif b43_val in (0x1, 0xD, 0x9):
                b43_real = 1
            elif b43_val in (0x2, 0xE, 0xA):
                b43_real = 2
            elif b43_val in (0x3, 0xF, 0xB):
                b43_real = 3
            else:
                b43_real = None  # valor inválido

            jogadores.append({
                "id": i,
                "nome": nome,
                "sobrenome": sobrenome,
                "idade": idade,
                "id_invertido": id_invertido,
                "time": nome_time,
                "passe": nome_passe,
                "finalizacoes": nome_finalizacoes,
                "cruzamentos": nome_cruzamentos,
                "tiroslongos": nome_tiroslongos,
                "drible": nome_drible,
                "recepcao": nome_recepcao,
                "posicao1": nome_pos1,
                "posicao2": nome_pos2,
                "posicao3": nome_posicao3,
                "posicao4": nome_pos4,
                "goleiro": is_goleiro,
                "movimento": nome_movimento,
                "forca": nome_forca,
                "ritmo": nome_ritmo,
                "energia": nome_energia,
                "cabeceio": nome_cabeceio,
                "roubada": nome_roubada,
                "marcacao": nome_marcacao,
                "pos_def": nome_pos_def,
                "lideranca": nome_lideranca,
                "criatividade": nome_criatividade,
                "penaltis": penaltis,
                "escanteios": escanteios,
                "nacionalidade": nacionalidade_nome,
            })
    return jogadores

# ----------------------------
# Escrita dos jogadores
# ----------------------------
def salvar_jogador(id, nome, sobrenome, idade=None, passe=None, finalizacoes=None, cruzamentos=None,
                   posicao1=None, posicao2=None, posicao3=None, posicao4=None, goleiro=None,
                   tiroslongos=None, drible=None, recepcao=None, movimento=None, forca=None,
                   ritmo=None, energia=None, cabeceio=None, roubada=None, marcacao=None, pos_def=None,
                   lideranca=None, criatividade=None, penaltis=None, escanteios=None):
    print(f"[DEBUG] Valor recebido em posicao3: {posicao3}")

    with open(get_arquivo_usuario(), "r+b") as f:
        pos = OFFSET_INICIAL + id * TAMANHO_JOGADOR

        # Ler todo o bloco uma única vez
        f.seek(pos)
        dados = bytearray(f.read(TAMANHO_JOGADOR))
        print(f"[ANTES] ID {id}: 41={dados[41]:02X}, 42={dados[42]:02X}, 43={dados[43]:02X}")

        # Nome
        nome_bytes = nome.encode("utf-8")[:NOME_LEN]
        nome_bytes += b'\x00' * (NOME_LEN - len(nome_bytes))
        dados[0:NOME_LEN] = nome_bytes

        # Sobrenome
        sobrenome_bytes = sobrenome.encode("utf-8")[:SOBRENOME_LEN]
        sobrenome_bytes += b'\x00' * (SOBRENOME_LEN - len(sobrenome_bytes))
        dados[NOME_LEN:NOME_LEN + SOBRENOME_LEN] = sobrenome_bytes

        # Idade (41 e parte baixa de 42)
        if idade and idade != "NENHUM":
            if idade in idades_dict:
                valor = idades_dict[idade][1]
                byte41 = valor & 0xFF
                byte42 = valor >> 8
                if dados[41] != byte41 or (dados[42] & 0x0F) != (byte42 & 0x0F):
                    dados[41] = byte41
                    dados[42] = (dados[42] & 0xF0) | (byte42 & 0x0F)
                    print(f"[DEBUG] Idade atualizada para {idade} (0x{byte41:02X} {byte42 & 0x0F:01X})")
                else:
                    print("[DEBUG] Idade não alterada, bytes mantidos.")
            else:
                print(f"[ERRO] Idade '{idade}' não encontrada no dicionário.")
        else:
            print("[DEBUG] Idade ignorada (valor NENHUM ou vazio)")

        # Passe
        if passe:
            dados[121] = passe_dict.get(passe, 0)

        # Finalizações
        if finalizacoes:
            dados[122] = finalizacoes_dict.get(finalizacoes, 0)

        # Cruzamentos
        if cruzamentos:
            dados[116] = cruzamentos_dict.get(cruzamentos, 0)

        # Tiros Longos
        if tiroslongos:
            dados[124] = tiroslongos_dict.get(tiroslongos, 0)

        # Drible
        if drible:
            dados[117] = drible_dict.get(drible, 0)

        # Recepção
        if recepcao:
            dados[118] = recepcao_dict.get(recepcao, 0)

        # Movimento (125)
        if movimento and movimento in movimento_dict:
            dados[125] = movimento_dict[movimento]

        # Força (73)
        if forca and forca in forca_dict:
            dados[73] = forca_dict[forca]

        # Ritmo (70:71)
        if ritmo and ritmo in ritmo_dict:
            dados[70:72] = ritmo_dict[ritmo]

        # Energia (72)
        if energia and energia in energia_dict:
            dados[72] = energia_dict[energia]

        # Cabeceio (119)
        if cabeceio and cabeceio in cabeceio_dict:
            dados[119] = cabeceio_dict[cabeceio]

        # Roubada (123)
        if roubada and roubada in roubada_dict:
            dados[123] = roubada_dict[roubada]

        # Marcação (120)
        if marcacao and marcacao in marcacao_dict:
            dados[120] = marcacao_dict[marcacao]

        # Pos def (69)
        if pos_def and pos_def in pos_def_dict:
            dados[69] = pos_def_dict[pos_def]

        # Liderança (74)
        if lideranca and lideranca in lideranca_dict:
            dados[74] = lideranca_dict[lideranca]

        # Criatividade (68)
        if criatividade and criatividade in criatividade_dict:
            dados[68] = criatividade_dict[criatividade]

        # Pênaltis/Faltas (1 byte)
        if penaltis and penaltis != "NENHUM" and penaltis in penaltis_dict:
            novo_val = penaltis_dict[penaltis]
            if dados[67] != novo_val:
                dados[67] = novo_val
                print(f"[DEBUG] Pênaltis atualizado para {penaltis} (0x{novo_val:02X})")
            else:
                print("[DEBUG] Pênaltis não alterado, byte mantido.")
        else:
            print("[DEBUG] Pênaltis ignorado (valor NENHUM ou vazio)")

        # Escanteios (1 byte)
        if escanteios and escanteios != "NENHUM" and escanteios in escanteios_dict:
            novo_val = escanteios_dict[escanteios]
            if dados[133] != novo_val:
                dados[133] = novo_val
                print(f"[DEBUG] Escanteios atualizado para {escanteios} (0x{novo_val:02X})")
            else:
                print("[DEBUG] Escanteios não alterado, byte mantido.")
        else:
            print("[DEBUG] Escanteios ignorado (valor NENHUM ou vazio)")

        # Goleiro
        if goleiro:
            if goleiro == "SIM":
                dados[39] = 0x80
                dados[79] = 0xE0
            else:
                dados[39] = 0x00
                dados[79] = 0x20

        # Posição 1
        if posicao1:
            val1, val2 = posicoes1_dict.get(posicao1, (0, 0))
            dados[82] = val1
            dados[83] = val2

        # Posição 2
        if posicao2:
            dados[95] = posicoes2_dict.get(posicao2, 0)

        # dado[43] = (nibble_alto << 4) | nibble_baixo

        # Posição 3 (offset 43 - nibble alto)
        if posicao3:
            print(f"[DEBUG salvar_jogador] Processando posicao3: {posicao3}")

            # Byte atual do offset 43
            byte_43 = dados[43]
            nibble_baixo = byte_43 & 0x0F
            nibble_alto_atual = (byte_43 & 0xF0) >> 4

            # Identificar grupo do nibble alto atual
            grupo_atual = None
            for grupo in grupos_43.keys():
                if nibble_alto_atual in grupo:
                    grupo_atual = grupo
                    break

            if grupo_atual is None:
                print(f"[ERRO salvar_jogador] Nibble alto atual {nibble_alto_atual:X} não pertence a nenhum grupo conhecido.")
            else:
                print(f"[DEBUG] nibble alto atual: {nibble_alto_atual:X}, grupo encontrado: {grupo_atual}")

                # Mapear o nome para nibble dentro do grupo atual
                nomes_do_grupo = grupos_43[grupo_atual]

                if posicao3 not in nomes_do_grupo:
                    print(f"[ERRO salvar_jogador] posicao3 '{posicao3}' não pertence ao grupo atual {grupo_atual}")
                else:
                    idx = nomes_do_grupo.index(posicao3)
                    nibble_novo = grupo_atual[idx]

                    # Montar novo byte mantendo nibble baixo original
                    novo_byte_43 = (nibble_novo << 4) | nibble_baixo
                    dados[43] = novo_byte_43

                    print(f"[DEBUG] nibble alto alterado para {nibble_novo:X} dentro do grupo {grupo_atual}")
                    print(f"[DEBUG] byte 43 atualizado de {byte_43:02X} para {novo_byte_43:02X}")

        # Posição 4
        if posicao4:
            grupo_atual = next((grupo for grupo in grupo_63 if posicao4 in grupo_63[grupo]), None)
            if grupo_atual:
                novo_val63 = grupo_atual[grupo_63[grupo_atual].index(posicao4)]
                dados[63] = novo_val63

        f.seek(pos)
        f.write(dados)

# ----------------------------
# Rotas
# ----------------------------
@app.route('/')
def index():
    if not os.path.isfile(get_arquivo_usuario()):
        return redirect(url_for('upload'))

    busca = request.args.get('busca', '').lower()
    busca_time = request.args.get('time', '').lower()
    jogadores = ler_jogadores()

    if busca:
        jogadores = [
            j for j in jogadores
            if busca in j["nome"].lower() or busca in j["sobrenome"].lower()
        ]

    if busca_time:
        jogadores = [
            j for j in jogadores
            if busca_time in j["time"].lower()
        ]

    return render_template("index.html", jogadores=jogadores, busca=busca, nacionalidades=nacionalidade2_dict.keys(),)

@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    jogadores = ler_jogadores()
    jogador = next((j for j in jogadores if j["id"] == id), None)
    if not jogador:
        return "Jogador não encontrado", 404

    if jogador["goleiro"]:
        jogador["goleiro"] = "SIM"
    else:
        jogador["goleiro"] = "NÃO"

    if request.method == "POST":
        print("[DEBUG] Valor recebido em posicao3:", request.form.get("posicao3"))
        nome = request.form.get("nome", "")
        sobrenome = request.form.get("sobrenome", "")
        idade = request.form.get("idade", None)
        passe = request.form.get("passe", "")
        finalizacoes = request.form.get("finalizacoes", "")
        cruzamentos = request.form.get("cruzamentos", "")
        tiroslongos = request.form.get("tiroslongos", "")
        drible = request.form.get("drible", "")
        recepcao = request.form.get("recepcao", "")
        goleiro = request.form.get("goleiro", "NÃO")
        posicao1 = request.form.get("posicao1", "NADA")
        posicao2 = request.form.get("posicao2", "VAZIO")
        posicao3 = request.form.get("posicao3")
        posicao4 = request.form.get("posicao4")
        movimento = request.form.get("movimento")
        forca = request.form.get("forca")
        ritmo = request.form.get("ritmo")
        energia = request.form.get("energia")
        cabeceio = request.form.get("cabeceio")
        roubada = request.form.get("roubada")
        marcacao = request.form.get("marcacao")
        pos_def = request.form.get("pos_def")
        lideranca = request.form.get("lideranca")
        criatividade = request.form.get("criatividade")
        penaltis = request.form.get("penaltis")
        escanteios = request.form.get("escanteios")
        print(f"[DEBUG editar] Valor que será salvo em posicao3: {posicao3}")

        salvar_jogador(id, nome, sobrenome, idade, passe, finalizacoes, cruzamentos,
                       posicao1, posicao2, posicao3, posicao4, goleiro,
                       tiroslongos, drible, recepcao, movimento, forca, ritmo,
                       energia, cabeceio, roubada, marcacao, pos_def, lideranca, criatividade,
                       penaltis, escanteios)

        return redirect(url_for("index"))

    return render_template(
        "editar.html",
        jogador=jogador,
        nacionalidades=nacionalidade2_dict.keys(),
        idades=idades_dict.keys(),
        passes=passe_dict.keys(),
        finalizacoes=finalizacoes_dict.keys(),
        cruzamentos=cruzamentos_dict.keys(),
        tiroslongos=tiroslongos_dict.keys(),
        drible=drible_dict.keys(),
        recepcao=recepcao_dict.keys(),
        posicoes1=posicoes1_dict.keys(),
        posicoes2=posicoes2_dict.keys(),
        posicoes3=posicao3_opcoes,
        posicoes4=posicao4_opcoes,
        movimento=movimento_dict.keys(),
        forca=forca_dict.keys(), 
        ritmo=ritmo_dict.keys(), 
        energia=energia_dict.keys(), 
        cabeceio=cabeceio_dict.keys(), 
        roubada=roubada_dict.keys(), 
        marcacao=marcacao_dict.keys(), 
        pos_def=pos_def_dict.keys(), 
        lideranca=lideranca_dict.keys(), 
        criatividade=criatividade_dict.keys(), 
        penaltis_dict=penaltis_dict,
        escanteios_dict=escanteios_dict,
    )

@app.route("/atualizar_contrato/<int:id>/<int:anos>", methods=["POST"])
def atualizar_contrato(id, anos):
    pos = OFFSET_INICIAL + id * TAMANHO_JOGADOR
    with open(get_arquivo_usuario(), "r+b") as f:
        f.seek(pos + 104)  # ⚠️ Offset de contrato — confirme se é o mesmo do seu script original
        f.write(bytes([anos]))
    return redirect(url_for("editar", id=id))

# ✅ NOVA ROTA PARA AUMENTAR VALOR DO JOGADOR
@app.route("/aumentar_valor/<int:id>", methods=["POST"])
def aumentar_valor(id):
    pos = OFFSET_INICIAL + id * TAMANHO_JOGADOR
    with open(get_arquivo_usuario(), "r+b") as f:
        f.seek(pos + 66)
        f.write(bytes([0xFF]))
        f.seek(pos + 105)
        f.write(bytes([0xFF]))
    return redirect(url_for("editar", id=id))


# ✅ NOVA ROTA PARA REDUZIR VALOR DO JOGADOR
@app.route("/reduzir_valor/<int:id>", methods=["POST"])
def reduzir_valor(id):
    pos = OFFSET_INICIAL + id * TAMANHO_JOGADOR
    with open(get_arquivo_usuario(), "r+b") as f:
        f.seek(pos + 66)
        f.write(bytes([0x00]))
        f.seek(pos + 105)
        f.write(bytes([0x00]))
    return redirect(url_for("editar", id=id))

@app.route("/salvar_nacionalidade/<int:id>", methods=["POST"])
def salvar_nacionalidade(id):
    nacionalidade = request.form.get("nacionalidade")
    if nacionalidade not in nacionalidade2_dict:
        return "Nacionalidade inválida", 400

    with open(get_arquivo_usuario(), "r+b") as f:
        pos = OFFSET_INICIAL + id * TAMANHO_JOGADOR
        f.seek(pos)
        dados = bytearray(f.read(TAMANHO_JOGADOR))

        hexstr = nacionalidade2_dict[nacionalidade].replace(" ", "")
        if len(hexstr) == 6:
            dados[41] = int(hexstr[0:2], 16)
            dados[42] = int(hexstr[2:4], 16)
            dados[43] = int(hexstr[4:6], 16)

            f.seek(pos)
            f.write(dados)

    return redirect(url_for("editar", id=id))

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'arquivo' not in request.files:
            return "Nenhum arquivo enviado", 400
        file = request.files['arquivo']
        if file.filename == '':
            return "Nenhum arquivo selecionado", 400
        ext = os.path.splitext(file.filename)[1]
        unique_name = f"{uuid.uuid4().hex}{ext}"
        caminho = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
        file.save(caminho)
        session['arquivo_usuario'] = caminho
        return redirect(url_for('index'))
    return render_template('upload.html')

# ✅ NOVA ROTA PARA DOWNLOAD DO ARQUIVO EDITADO
from flask import send_file

@app.route('/upload', methods=['POST'])
def upload_arquivo():
    if 'arquivo' not in request.files:
        flash('Nenhum arquivo selecionado.')
        return redirect(url_for('index'))

    arquivo = request.files['arquivo']

    if arquivo.filename == '':
        flash('Nenhum arquivo selecionado.')
        return redirect(url_for('index'))

    # Usando secure_filename para evitar problemas de nomes
    filename = secure_filename(arquivo.filename)
    caminho_salvar = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    arquivo.save(caminho_salvar)

    flash('Arquivo enviado com sucesso!')
    return redirect(url_for('index'))

@app.route("/download")
def download():
    caminho = get_arquivo_usuario()
    nome_sugerido = os.path.basename(caminho)
    return send_file(caminho, as_attachment=True, download_name=nome_sugerido)

if __name__ == "__main__":
    app.run(debug=True)
