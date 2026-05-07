import os
from datetime import datetime, timedelta, date

import requests
from database import get_connection


def fahrenheit_to_celcius(temp):
    if temp is not None:
        return round((temp - 32) * 5 / 9, 2)
    return None


def mph_to_kmph(v_mph):
    if v_mph is not None:
        return round(v_mph * 1.609, 2)
    return None


def validar_nome_cidade(cidade):
    if not cidade or not isinstance(cidade, str):
        return 'O nome da cidade é obrigatório.'

    if len(cidade.strip()) < 2:
        return 'O nome da cidade deve ter pelo menos 2 caracteres'

    return None


def buscar_no_banco(cidade):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        hoje = date.today()

        cursor.execute("""
            SELECT cidade, data, umidade, vento, precipitacao, temp_min, temp_max
            FROM historico_clima
            WHERE cidade = %s AND data = %s
        """, (cidade, hoje))

        resultado = cursor.fetchone()

        cursor.close()
        conn.close()

        if resultado:
            return {
                'cidade': resultado[0],
                'data': resultado[1].strftime('%d/%m/%Y'),
                'umidade': resultado[2],
                'vento': resultado[3],
                'precipitacao': resultado[4],
                'temperatura_min': resultado[5],
                'temperatura_max': resultado[6],
                'from_db': True
            }

        return None

    except Exception as e:
        print("Erro ao buscar no banco:", e)
        return None


def transformar_dados_clima(dados_clima):
    clima_atual = dados_clima.get('currentConditions', {})
    dias = dados_clima.get('days', [])[:7]

    data_atual = datetime.now().strftime('%d/%m/%Y')

    dados_processados = {
        'data': data_atual,
        'hora': clima_atual.get('datetime'),
        'cidade': dados_clima.get('resolvedAddress'),
        'temperatura': fahrenheit_to_celcius(clima_atual.get('temp')),
        'umidade': clima_atual.get('humidity'),
        'vento': mph_to_kmph(clima_atual.get('windspeed')),
        'precipitacao': clima_atual.get('precip'),
        'icon': clima_atual.get('icon'),
        'previsao': []
    }

    for dia in dias:
        dia_processado = {
            'data': datetime.strptime(dia['datetime'], "%Y-%m-%d").strftime('%d/%m/%Y'),
            'temperatura_max': fahrenheit_to_celcius(dia.get('tempmax')),
            'temperatura_min': fahrenheit_to_celcius(dia.get('tempmin')),
            'umidade': dia.get('humidity'),
            'vento': mph_to_kmph(dia.get('windspeed')),
            'precipitacao': dia.get('precip'),
            'icon': dia.get('icon'),
        }

        dados_processados['previsao'].append(dia_processado)

    return dados_processados


def salvar_no_banco(clima):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        hoje = date.today()

        cursor.execute("""
            SELECT 1 FROM historico_clima
            WHERE cidade = %s AND data = %s
        """, (clima.get('cidade'), hoje))

        existe = cursor.fetchone()

        if not existe:
            cursor.execute("""
                INSERT INTO historico_clima 
                (cidade, data, umidade, vento, precipitacao, temp_min, temp_max)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                clima.get('cidade'),
                hoje,
                clima.get('umidade'),
                clima.get('vento'),
                clima.get('precipitacao'),
                clima.get('previsao')[0].get('temperatura_min') if clima.get('previsao') else None,
                clima.get('previsao')[0].get('temperatura_max') if clima.get('previsao') else None
            ))

            conn.commit()
            print("Salvo no banco!")
        else:
            print("Já existe no banco")

        cursor.close()
        conn.close()

    except Exception as e:
        print("Erro ao salvar:", e)


def buscar_clima_por_cidade(cidade):
    msg_erro = validar_nome_cidade(cidade)
    if msg_erro:
        return {'error': True, 'message': msg_erro}

    dados_banco = buscar_no_banco(cidade)

    if dados_banco:
        print("VEIO DO BANCO")
        return {'error': False, 'data': dados_banco}

    base_url = os.getenv('BASE_URL_VISUAL_CROSSING')
    api_key = os.getenv('VISUAL_CROSSING_API_KEY')

    data_inicial = datetime.now().strftime('%Y-%m-%d')
    data_final = (datetime.now() + timedelta(days=6)).strftime('%Y-%m-%d')

    url = f"{base_url}{cidade}/{data_inicial}/{data_final}?key={api_key}&unitGroup=us&include=days,current"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        dados = response.json()
        dados_transformados = transformar_dados_clima(dados)

        print("VEIO DA API")

        salvar_no_banco(dados_transformados)

        return {'error': False, 'data': dados_transformados}

    except Exception as e:
        return {'error': True, 'message': str(e)}