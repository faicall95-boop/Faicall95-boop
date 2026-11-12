import os
import urllib.request
import urllib.parse
import json
import time
import ssl
import threading
from flask import Flask

# ==========================================
# 🔑 CONFIGURATION TELEGRAM & CAPITAL
# ==========================================
# ⚠️ REMPLACE CES VALEURS PAR LES TIENNES
TELEGRAM_TOKEN = "8800937654:AAHlICl2JWAPQf5glyB9W6kSXqywNyA4QuE" 
TELEGRAM_CHAT_ID = "617879156"

# 💰 CONFIGURATION DU TRADING
CAPITAL_TOTAL = 10000.0  # Ton capital de départ
RISQUE_POURCENT = 1.0    # Tu risques 1% par trade (donc 100$ max)

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
    
    if buys >= 3 and tendance_haussiere:
        return "🟢 **ACHAT FORT**"
    if sells >= 3:
        return "🔴 **VENTE FORTE**"
    if sells >= 3 and tendance_baissiere:
        return "🔴 **VENTE FORTE CONFIRMÉE**"
    return "⚪ ATTENDRE"

# ==========================================
# PARTIE 3 : RÉCUPÉRATION DES PRIX (1H) & ATR
# ==========================================
def recuperer_donnees_yahoo(symbole):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbole}?interval=1h&range=1mo"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        context = ssl._create_unverified_context()
        req = urllib.request.Request(url, headers=headers)
        requete = urllib.request.urlopen(req, timeout=10, context=context)
        donnees = json.loads(requete.read().decode('utf-8'))
        resultat = donnees['chart']['result'][0]
        prix_cloture = resultat['indicators']['quote'][0]['close']
        prix_haut = resultat['indicators']['quote'][0]['high']
        prix_bas = resultat['indicators']['quote'][0]['low']
        
        # On nettoie les données vides
        closes = [p for p in prix_cloture if p is not None]
        highs = [p for p in prix_haut if p is not None]
        lows = [p for p in prix_bas if p is not None]
        
        return closes, highs, lows
    except Exception as e:
        return [], [], []

def calculer_atr(highs, lows, closes, periode=14):
    """Calcule l'Average True Range (Volatilité)"""
    if len(closes) < periode + 1: return 0
    tr_list = []
    for i in range(-periode, 0):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        tr_list.append(tr)
    return sum(tr_list) / periode

# ==========================================
# PARTIE 4 : CALCULATEUR DE LOTS (SL via ATR)
# ==========================================
def calculer_taille_position(nom_actif, prix_entree, atr):
    """
    Calcule la taille de la position en fonction du risque (100$),
    et d'un Stop-Loss placé à 2 fois l'ATR.
    """
    risque_max_usd = CAPITAL_TOTAL * (RISQUE_POURCENT / 100)
    distance_sl = atr * 2 # Stop Loss à 2x l'ATR
    
    if distance_sl == 0:
        return "Erreur ATR", 0

    # Définition du prix du SL
    prix_sl = prix_entree - distance_sl # On suppose un achat (Long)
    
    if "EURUSD" in nom_actif or "GBPUSD" in nom_actif or "USDJPY" in nom_actif or "USDCHF" in nom_actif:
        # Forex : 1 lot standard = 100 000. 1 pip = 0.0001 (sauf JPY)
        pip_valeur = 10 if "JPY" not in nom_actif else 6.5
        distance_pips = distance_sl / (0.0001 if "JPY" not in nom_actif else 0.01)
        taille_lot = risque_max_usd / (distance_pips * pip_valeur)
        return f"{taille_lot:.2f} lots", prix_sl
        
    elif nom_actif == "GOLD":
        # Or : 1 lot standard = 100 onces. 1$ de mouvement = 100$ de perte.
        taille_lot = risque_max_usd / (distance_sl * 100)
        return f"{taille_lot:.2f} lots", prix_sl
        
    elif nom_actif in ["BTC", "ETH", "SOL"]:
        # Crypto : Calcul en unités directes
        taille_unites = risque_max_usd / distance_sl
        return f"{taille_unites:.4f} unités", prix_sl
        
    elif nom_actif in ["NASDAQ", "FR40", "DE40", "DJ"]:
        # Indices : 1 contrat = 1$ par point
        taille_contrats = risque_max_usd / distance_sl
        return f"{taille_contrats:.2f} contrats", prix_sl
        
    return "N/A", 0

# ==========================================
# PARTIE 5 : ENVOI TELEGRAM & LOGIQUE
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

def analyser_marche(nom, closes, highs, lows):
    if not closes or len(closes) < 96: return None
    votes = [
        agent_trend(closes), 
        agent_rsi(closes), 
        agent_macd(closes), 
        agent_smart_money(closes)
    ]
    buys = votes.count(1)
    sells = votes.count(-1)
    conseil_final = agent_conseil(closes, buys, sells)
    atr = calculer_atr(highs, lows, closes)
    
    return {
        "nom": nom, "prix": closes[-1], "buys": buys, "sells": sells, 
        "conseil": conseil_final, "atr": atr
    }

# ==========================================
# PARTIE 6 : LA BOUCLE DU BOT
# ==========================================
def boucle_bot():
    print("🌍 Bot ULTIME (1H) avec ATR et Calculateur de Lots démarré...")
    envoyer_alerte_telegram(f"🌍 *Bot ULTIME activé !* Capital : {CAPITAL_TOTAL}$ | Risque max : {CAPITAL_TOTAL * (RISQUE_POURCENT/100)}$ | Stop-Loss : 2x ATR.")

    derniers_signaux_forts = {
        "BTC": "", "ETH": "", "SOL": "",
        "GOLD": "", "NASDAQ": "", "FR40": "", "DE40": "", "DJ": "",
        "EURUSD": "", "GBPUSD": "", "USDJPY": "", "USDCHF": ""
    }
    
    while True:
        print(f"\n--- Analyse 1H {time.strftime('%H:%M:%S')} ---")
        
        # Liste des actifs à analyser
        actifs = {
            "BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD",
            "GOLD": "GC=F", "NASDAQ": "NQ=F", "FR40": "^FCHI", 
            "DE40": "^GDAXI", "DJ": "^DJI",
            "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", 
            "USDJPY": "USDJPY=X", "USDCHF": "USDCHF=X"
        }
        
        resultats = []
        for nom, symbole in actifs.items():
            closes, highs, lows = recuperer_donnees_yahoo(symbole)
            res = analyser_marche(nom, closes, highs, lows)
            if res: resultats.append(res)
        
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

                    # Calcul de la taille et du SL
                    taille_pos, prix_sl = calculer_taille_position(nom, r['prix'], r['atr'])

                    msg_alerte = (
                        f"{titre}\n\n"
                        f"{emoji} Actif : *{nom}*\n"
                        f"💰 Prix d'entrée : `{r['prix']:.4f} $`\n"
                        f"📊 Consensus : Achats {r['buys']}/4 | Ventes {r['sells']}/4\n\n"
                        f"🛑 *Stop-Loss suggéré (2x ATR)* :\n"
                        f"👉 `{prix_sl:.4f} $`\n\n"
                        f"📦 *Taille de position (Risque 1%)* :\n"
                        f"👉 `{taille_pos}`\n\n"
                        f"⚠️ *Action* : {action}"
                    )
                    envoyer_alerte_telegram(msg_alerte)
                    derniers_signaux_forts[nom] = "DEJA_ENVOYE"
            else:
                derniers_signaux_forts[nom] = ""

        print("✅ Analyse terminée. Attente de 1 heure...")
        time.sleep(3600) # Pause de 1 heure

# ==========================================
# LANCEMENT
# ==========================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    threading.Thread(target=boucle_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=port)
