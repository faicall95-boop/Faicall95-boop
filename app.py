import os
import urllib.request
import urllib.parse
import json
import time
import ssl
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
# PARTIE 1 : LES AGENTS D'ANALYSE (4H)
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

def agent_breakout(prices):
    if len(prices) < 21: return 0
    window = prices[-21:-1]
    if prices[-1] > max(window): return 1
    if prices[-1] < min(window): return -1
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

def agent_support_resistance(prices):
    if len(prices) < 50: return 0
    recent_prices = prices[-50:]
    plus_haut = max(recent_prices)
    plus_bas = min(recent_prices)
    prix_actuel = prices[-1]
    if prix_actuel <= plus_bas * 1.01: return 1
    elif prix_actuel >= plus_haut * 0.99: return -1
    return 0

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
# PARTIE 2 : L'AGENT DECISIONNEL
# ==========================================
def agent_conseil(prices, buys, sells):
    if len(prices) < 96: return "⏳ Données insuffisantes"
    prix_actuel = prices[-1]
    sma_50 = sum(prices[-50:]) / 50
    tendance_haussiere = prix_actuel > sma_50
    tendance_baissiere = prix_actuel < sma_50
    
    if buys >= 5 and tendance_haussiere:
        return "🟢 **ACHAT FORT**"
    if sells >= 5:
        return "🔴 **VENTE FORTE**"
    if sells >= 5 and tendance_baissiere:
        return "🔴 **VENTE FORTE CONFIRMÉE**"
    return "⚪ ATTENDRE"

# ==========================================
# PARTIE 3 : RÉCUPÉRATION DES PRIX (4H)
# ==========================================
def recuperer_prix_yahoo(symbole):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbole}?interval=4h&range=1mo"
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

# --- SCANNER CRYPTO < 2 CENTIMES ---
def scanner_cryptos_pas_cheres():
    cryptos_cibles = {
        "VANRY": "VANRY-USD",
        "CSPR": "CSPR-USD",
        "CORE": "CORE-USD",
        "ACT": "ACT-USD"
    }
    trouvailles = []
    for nom, symbole in cryptos_cibles.items():
        prix = recuperer_prix_yahoo(symbole)
        if prix and len(prix) > 0:
            dernier_prix = prix[-1]
            if dernier_prix < 0.02:
                trouvailles.append({
                    'nom': nom,
                    'prix': f"{dernier_prix:.6f}",
                    'url': f"https://finance.yahoo.com/quote/{symbole}"
                })
    return trouvailles

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
        agent_trend(prix), agent_rsi(prix), agent_breakout(prix), 
        agent_macd(prix), agent_support_resistance(prix), agent_smart_money(prix)
    ]
    buys = votes.count(1)
    sells = votes.count(-1)
    conseil_final = agent_conseil(prix, buys, sells)
    return {
        "nom": nom, "prix": prix[-1], "buys": buys, "sells": sells, "conseil": conseil_final
    }

# ==========================================
# PARTIE 5 : BOUCLE PRINCIPALE
# ==========================================
def boucle_bot():
    print("🌍 Bot ULTIME (4H) démarré. En attente de signaux forts...")
    envoyer_alerte_telegram("🌍 *Bot ULTIME activé (Mode 4 Heures) !* Je te préviendrai uniquement pour les ACHATS FORTS et VENTES FORTES.")

    derniers_signaux_forts = {
        "BTC": "", "ETH": "", "SOL": "",
        "GOLD": "", "NASDAQ": "", "FR40": "", "DE40": "", "DJ": "",
        "EURUSD": "", "GBPUSD": "", "USDJPY": "", "USDCHF": ""
    }
    cryptos_deja_annoncees = set()
    compteur_minutes = 0
    
    while True:
        print(f"\n--- Analyse 4H {time.strftime('%H:%M:%S')} ---")
        
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
                        titre = "🚀🚀 *SIGNAL D'ACHAT FORT (4H)* 🚀🚀"
                        action = "Opportunité d'entrée. Place ton Stop-Loss !"
                    else:
                        titre = "🩸🩸 *SIGNAL DE VENTE FORTE (4H)* 🩸🩸"
                        action = "Le marché se retourne ! Vends ou sécurise tes gains."

                    msg_alerte = (
                        f"{titre}\n\n"
                        f"{emoji} Actif : *{nom}*\n"
                        f"💰 Prix : `{r['prix']:.4f} $`\n"
                        f"📊 Consensus : Achats {r['buys']}/6 | Ventes {r['sells']}/6\n"
                        f"📈 Tendance : {'Haussière' if 'ACHAT' in r['conseil'] else 'Baissière'}\n\n"
                        f"⚠️ *Action* : {action}"
                    )
                    envoyer_alerte_telegram(msg_alerte)
                    derniers_signaux_forts[nom] = "DEJA_ENVOYE"
            else:
                derniers_signaux_forts[nom] = ""

        compteur_minutes += 1
        if compteur_minutes % 30 == 0:
            print("🔎 Scan des cryptos à moins de 2 centimes...")
            trouvailles = scanner_cryptos_pas_cheres()
            for crypto in trouvailles:
                if crypto['nom'] not in cryptos_deja_annoncees:
                    msg = f"🪙 *Crypto à moins de 2 centimes repérée*\n\n"
                    msg += f"🆔 *{crypto['nom']}*\n"
                    msg += f"💰 Prix actuel : `{crypto['prix']} $`\n\n"
                    msg += f"🔗 [Voir le graphique]({crypto['url']})\n"
                    msg += f"⚠️ *Très volatile. Fais tes recherches.*"
                    envoyer_alerte_telegram(msg)
                    cryptos_deja_annoncees.add(crypto['nom'])
                    print(f"✅ Crypto signalée : {crypto['nom']}")

        time.sleep(60)

# ==========================================
# LANCEMENT DU BOT
# ==========================================
# On lance le bot directement (plus de Thread pour éviter les crashs sur Render)
print("🚀 BOT EN COURS DE DEMARRAGE...")
boucle_bot()

# Ce code ne sera jamais atteint à cause de la boucle infinie au-dessus, 
# mais on le garde pour Render qui exige un port HTTP
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
