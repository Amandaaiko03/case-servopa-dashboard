import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Configurações iniciais da página
st.set_page_config(page_title="Gestão de Bônus - Servopa", layout="wide")

# CSS com as cores da servopa
st.markdown("""
    <style>
    .stApp {
        background-color: #f5f5f5;
    }
    [data-testid="stMetric"] {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #002b5c;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    h1, h2, h3 {
        color: #002b5c !important;
    }
    </style>
    """, unsafe_allow_html=True)

caminho_arquivo = "controle_de_bonus_case.xlsx"

@st.cache_data
def carregar_dados():
    vendas = pd.read_excel(caminho_arquivo, sheet_name="Vendas")
    campanhas = pd.read_excel(caminho_arquivo, sheet_name="Campanhas")
    bonus = pd.read_excel(caminho_arquivo, sheet_name="Controle_de_Bonus")
    pos_venda = pd.read_excel(caminho_arquivo, sheet_name="Pos_Venda")
    filiais = pd.read_excel(caminho_arquivo, sheet_name="dim_filiais")
    
    # SANEAMENTO DE DADOS 
    colunas_fin = ['Margem_liquida_pre_bonus', 'Margem_liquida_pos_bonus']
    for col in colunas_fin:
        # Converte para número e remove erros de preenchimento 
        vendas[col] = pd.to_numeric(vendas[col], errors='coerce')

        vendas.loc[vendas[col] > 1000000, col] = 0
        vendas[col] = vendas[col].fillna(0)
    
    bonus['Data_envio'] = pd.to_datetime(bonus['Data_envio'])
    vendas['Data_venda'] = pd.to_datetime(vendas['Data_venda'])
    
    # Unir bônus com campanhas para saber o valor previsto
    df_bonus_full = pd.merge(bonus, campanhas[['Campanha', 'Valor_bonus', 'Marca']], on='Campanha', how='left')
    df_bonus_full['Valor_bonus'] = pd.to_numeric(df_bonus_full['Valor_bonus'], errors='coerce').fillna(0)
    
    # Calcular Valor em Risco
    df_bonus_full['Valor_em_Risco'] = df_bonus_full.apply(
        lambda x: x['Valor_bonus'] if x['Status'] in ['Pendente', 'Enviado', 'Recusado'] else 0, axis=1
    )
    
    # Unir Vendas com Filiais 
    vendas = pd.merge(vendas, filiais[['Filial_ID', 'Filial']], on='Filial_ID', how='left', suffixes=('', '_dim'))
    
    return vendas, df_bonus_full, pos_venda, filiais

# Carregar os dataframes
df_vendas, df_bonus, df_pos, df_filiais = carregar_dados()

# Sidebar para filtros
st.sidebar.markdown(f"<h1 style='text-align: center; color: #002b5c;'>GRUPO SERVOPA</h1>", unsafe_allow_html=True)
st.sidebar.markdown("---")
st.sidebar.header("Painel de Filtros")

data_min = df_vendas['Data_venda'].min().to_pydatetime()
data_max = df_vendas['Data_venda'].max().to_pydatetime()
periodo = st.sidebar.date_input("Período de Venda", value=[data_min, data_max], min_value=data_min, max_value=data_max)

marcas = st.sidebar.multiselect("Marcas", options=df_vendas['Marca'].unique(), default=df_vendas['Marca'].unique())
filiais_sel = st.sidebar.multiselect("Filiais", options=df_filiais['Filial'].unique(), default=df_filiais['Filial'].unique())

# Filtros aplicados
if len(periodo) == 2:
    mask = (df_vendas['Data_venda'].dt.date >= periodo[0]) & (df_vendas['Data_venda'].dt.date <= periodo[1]) & \
           (df_vendas['Marca'].isin(marcas)) & (df_vendas['Filial'].isin(filiais_sel))
else:
    mask = (df_vendas['Marca'].isin(marcas)) & (df_vendas['Filial'].isin(filiais_sel))

df_vendas_f = df_vendas[mask]
chassis_f = df_vendas_f['Chassi'].unique()
df_bonus_f = df_bonus[df_bonus['Chassi'].isin(chassis_f)]
df_pos_f = df_pos[df_pos['Chassi'].isin(chassis_f)]

# Titulos
st.title("📊 Controladoria: Gestão de Bônus e Performance")
st.subheader("Grupo Servopa - Relatório Executivo")

# KPIs
total_recebido = df_bonus_f[df_bonus_f['Status'] == 'Aprovado']['Valor_recebido'].sum()
valor_risco = df_bonus_f['Valor_em_Risco'].sum()
nps_medio = df_pos_f['NPS'].mean() if not df_pos_f.empty else 0

def formatar_brl(valor):
    if abs(valor) >= 1_000_000: return f"R$ {valor/1_000_000:.2f}M"
    if abs(valor) >= 1_000: return f"R$ {valor/1_000:.1f}k"
    return f"R$ {valor:,.2f}"

k1, k2, k3, k4 = st.columns(4)
k1.metric("Bônus Recebido", formatar_brl(total_recebido))
k2.metric("Valor em Risco", formatar_brl(valor_risco), delta="Atenção", delta_color="inverse")
k3.metric("NPS Médio", f"{nps_medio:.1f}")
k4.metric("Vendas Período", len(df_vendas_f))

st.markdown("---")

# Cor dos Gráficos
azul_servopa = "#002b5c"
cinza_servopa = "#8e9091"

c1, c2 = st.columns(2)

with c1:
    st.subheader("💰 Performance de Margem por Marca")
    
    # Agrupamos por Marca usando a base de vendas limpa 
    margem_data = df_vendas_f.groupby('Marca')[['Margem_liquida_pre_bonus', 'Margem_liquida_pos_bonus']].sum().reset_index()
    
    # Gráfico
    fig_margem = px.bar(margem_data, 
                        x='Marca', 
                        y=['Margem_liquida_pre_bonus', 'Margem_liquida_pos_bonus'],
                        labels={'value': 'Valor Total (R$)', 'variable': 'Tipo de Margem'},
                        barmode='group', 
                        color_discrete_sequence=[cinza_servopa, azul_servopa])
    
    # Formatando o Eixo Y e legenda
    fig_margem.update_layout(
        yaxis=dict(tickformat=",.2f"), 
        plot_bgcolor='rgba(0,0,0,0)',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig_margem, use_container_width=True)

with c2:
    st.subheader("⚠️ Gargalos: Atrasos de Envio")
    atrasos = df_bonus_f.groupby('Filial_ID')['Flag_envio_fora_prazo'].sum().reset_index()
    fig_atraso = px.bar(atrasos, x='Filial_ID', y='Flag_envio_fora_prazo', color_discrete_sequence=['#d32f2f'])
    fig_atraso.update_layout(plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_atraso, use_container_width=True)

st.markdown("---")

# Tabela de Prioridades
st.subheader("🚨 Plano de Ação: Top 10 Prioridades (Controladoria)")

df_prioridade = df_bonus_f[df_bonus_f['Status'].isin(['Pendente', 'Enviado'])].sort_values(by='Valor_em_Risco', ascending=False)
top_10 = df_prioridade[['Chassi', 'Campanha', 'Tipo_bonus', 'Status', 'Valor_em_Risco', 'Flag_envio_fora_prazo']].head(10)

# Estilo para destacar atrasos na tabela
def highlight_atraso(row):
    return ['background-color: #ffebee' if row['Flag_envio_fora_prazo'] == 1 else '' for _ in row]

st.dataframe(
    top_10.style.apply(highlight_atraso, axis=1),
    use_container_width=True,
    hide_index=True,
    column_config={
        "Valor_em_Risco": st.column_config.NumberColumn("Valor em Risco", format="R$ %.2f"),
        "Flag_envio_fora_prazo": st.column_config.CheckboxColumn("Vencido? 🚩")
    }
)