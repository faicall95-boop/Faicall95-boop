import os
import urllib.request
import urllib.parse
import json
import time
import ssl
import threading
from flask import Flask

# ==========================================
# 🔑 CONFIGURATION TELEGRAM
# ==========================================
# ⚠️ REMPLACE CES VALEURS PAR LES TIENNES
TELEGRAM_TOKEN = "8800937654:AAHlICl2JWAPQf5glyB9W6kSXqywNyA4QuE" 
TELEGRAM_CHAT_ID = "617879156"

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot en cours d'exécution !"

# ==========================================
# PARTIE 1 : LES AGENTS D'ANALYSE (1H) - 4 AGENTS
# ==========================================
def agent_trend(prices):
    if len(prices) < 20: return 0
    ma_fast = sum(prices[-5:]) / 5
    ma_slow = sum(prices[-20:]) / 20
    return 1 if ma_fast > ma_slow else -1

def agent_rsi(prices):
    if len(prices) < 15: return 0
    gains = losses = 0
    for i in range(-14, 0):
        diff = prices[i] - prices[i-1]
        if diff > 0: gains += diff
        else: losses -= diff
    rs = gains / (losses if losses != 0 else 1e-9)
    rsi = 100 - 100 / (1 + rs)
    if rsi < 30: return 1
    if rsi > 70: return -1
    return 0

def agent_macd(prices):
    if len(prices) < 26: return 0
    def ema(data, n):
        k = 2 / (n + 1)
        e = data[0]
        for p in data[1:]:
            e = p * k + e * (1 - k)
        return e
    macd = ema(prices, 12) - ema(prices, 26)
    return 1 if macd > 0 else -1

def agent_smart_money(prices):
    if len(prices) < 96: return 0
    prix_actuel = prices[-1]
    sma_20 = sum(prices[-20:]) / 20
    variance = sum((p - sma_20) ** 2 for p in prices[-20:]) / 20
    ecart_type = variance ** 0.5
    bb_superieure = sma_20 + (2 * ecart_type)
    bb_inferieure = sma_20 - (2 * ecart_type)
    plus_haut = max(prices[-96:])
    plus_bas = min(prices[-96:])
    fib_618 = plus_haut - ((plus_haut - plus_bas) * 0.618)
    
    if (fib_618 * 0.995 <= prix_actuel <= fib_618 * 1.005) and prix_actuel < sma_20:
        return 1
    if prix_actuel <= bb_inferieure * 0.998:
        return 1
    if prix_actuel >= bb_superieure * 0.998:
        return -1
    return 0

# ==========================================
# PARTIE 2 : L'AGENT DECISIONNEL (Règle du 3/4)
# ==========================================
def agent_conseil(prices, buys, sells):
    if len(prices) < 96: return "⏳ Données insuffisantes"
    prix_actuel = prices[-1]
    sma_50 = sum(prices[-50:]) / 50
    tendance_haussiere = prix_actuel > sma_50
    tendance_baissiere = prix_actuel < sma_50
    
    # ON EXIGE 3 VOTES SUR 4
    if buys >= 3 and tendance_haussiere:
        return "🟢 **ACHAT FORT**"
    if sells >= 3:
        return "🔴 **VENTE FORTE**"
    if sells >= 3 and tendance_baissiere:
        return "🔴 **VENTE FORTE CONFIRMÉE**"
    return "⚪ ATTENDRE"

# ==========================================
# PARTIE 3 : RÉCUPÉRATION DES PRIX (1H)
# ==========================================
def recuperer_prix_yahoo(symbole):
    # PASSAGE EN 1 HEURE ICI
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbole}?interval=1h&range=1mo"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        context = ssl._create_unverified_context()
        req = urllib.request.Request(url, headers=headers)
        requete = urllib.request.urlopen(req, timeout=10, context=context)
        donnees = json.loads(requete.read().decode('utf-8'))
        resultat = donnees['chart']['result'][0]
        prix = resultat['indicators']['quote'][0]['close']
        return [p for p in prix if p is not None]
    except Exception as e:
        return []

# ==========================================
# PARTIE 4 : ENVOI TELEGRAM & LOGIQUE
# ==========================================
def envoyer_alerte_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    data_encode = urllib.parse.urlencode(data).encode('utf-8')
    try:
        context = ssl._create_unverified_context()
        req = urllib.request.Request(url, data=data_encode)
        urllib.request.urlopen(req, timeout=10, context=context)
        print("✅ Message Telegram envoyé")
    except Exception as e:
        print(f"❌ Erreur Telegram : {e}")

def analyser_marche(nom, prix):
    if not prix or len(prix) < 96: return None
    
    votes = [
        agent_trend(prix), 
        agent_rsi(prix), 
        agent_macd(prix), 
        agent_smart_money(prix)
    ]
    
    buys = votes.count(1)
    sells = votes.count(-1)
    conseil_final = agent_conseil(prix, buys, sells)
    
    return {
        "nom": nom, "prix": prix[-1], "buys": buys, "sells": sells, "conseil": conseil_final
    }

# ==========================================
# PARTIE 5 : LA BOUCLE DU BOT
# ==========================================
def boucle_bot():
    print("🌍 Bot ULTIME (1H) démarré avec 4 agents (Règle 3/4). En attente de signaux...")
    envoyer_alerte_telegram("🌍 *Bot ULTIME activé (Mode 1 Heure) !* Je surveille les marchés de plus près.")

    derniers_signaux_forts = {
        "BTC": "", "ETH": "", "SOL": "",
        "GOLD": "", "NASDAQ": "", "FR40": "", "DE40": "", "DJ": "",
        "EURUSD": "", "GBPUSD": "", "USDJPY": "", "USDCHF": ""
    }
    
    while True:
        print(f"\n--- Analyse 1H {time.strftime('%H:%M:%S')} ---")
        
        res_btc = analyser_marche("BTC", recuperer_prix_yahoo("BTC-USD"))
        res_eth = analyser_marche("ETH", recuperer_prix_yahoo("ETH-USD"))
        res_sol = analyser_marche("SOL", recuperer_prix_yahoo("SOL-USD"))
        res_gold = analyser_marche("GOLD", recuperer_prix_yahoo("GC=F"))
        res_nasdaq = analyser_marche("NASDAQ", recuperer_prix_yahoo("NQ=F"))
        res_fr40 = analyser_marche("FR40", recuperer_prix_yahoo("^FCHI"))
        res_de40 = analyser_marche("DE40", recuperer_prix_yahoo("^GDAXI"))
        res_dj = analyser_marche("DJ", recuperer_prix_yahoo("^DJI"))
        res_eurusd = analyser_marche("EURUSD", recuperer_prix_yahoo("EURUSD=X"))
        res_gbpusd = analyser_marche("GBPUSD", recuperer_prix_yahoo("GBPUSD=X"))
        res_usdjpy = analyser_marche("USDJPY", recuperer_prix_yahoo("USDJPY=X"))
        res_usdchf = analyser_marche("USDCHF", recuperer_prix_yahoo("USDCHF=X"))
        
        resultats = [r for r in [res_btc, res_eth, res_sol, res_gold, res_nasdaq, res_fr40, res_de40, res_dj, res_eurusd, res_gbpusd, res_usdjpy, res_usdchf] if r is not None]
        
        for r in resultats:
            nom = r["nom"]
            if "ACHAT FORT" in r["conseil"] or "VENTE FORTE" in r["conseil"]:
                if derniers_signaux_forts.get(nom) != "DEJA_ENVOYE":
                    
                    if nom == "BTC": emoji = "₿"
                    elif nom in ["ETH", "SOL"]: emoji = "🪙"
                    elif nom == "GOLD": emoji = "🥇"
                    elif nom in ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]: emoji = "💱"
                    else: emoji = "📈"
                    
                    if "ACHAT" in r["conseil"]:
                        titre = "🚀🚀 *SIGNAL D'ACHAT FORT (1H)* 🚀🚀"
                        action = "Opportunité d'entrée. Place ton Stop-Loss !"
                    else:
                        titre = "🩸🩸 *SIGNAL DE VENTE FORTE (1H)* 🩸🩸"
                        action = "Le marché se retourne ! Vends ou sécurise tes gains."

                    msg_alerte = (
                        f"{titre}\n\n"
                        f"{emoji} Actif : *{nom}*\n"
                        f"💰 Prix : `{r['prix']:.4f} $`\n"
                        f"📊 Consensus : Achats {r['buys']}/4 | Ventes {r['sells']}/4\n\n"
                        f"⚠️ *Action* : {action}"
                    )
                    envoyer_alerte_telegram(msg_alerte)
                    derniers_signaux_forts[nom] = "DEJA_ENVOYE"
            else:
                derniers_signaux_forts[nom] = ""

        print("✅ Analyse terminée. Attente de 1 heure...")
        time.sleep(3600) # Pause de 1 heure (3600 secondes)

# ==========================================
# LANCEMENT
# ==========================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    
    threading.Thread(target=boucle_bot, daemon=True).start()
    
    app.run(host="0.0.0.0", port=port)
