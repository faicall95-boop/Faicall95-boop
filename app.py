import os
import urllib.request
import urllib.parse
import json
import time
import ssl
import threading
from flask import Flask

# ==========================================
# 🔑 CONFIGURATION
# ==========================================
TELEGRAM_TOKEN = os.environ.get('8800937654:AAHlICl2JWAPQf5glyB9W6kSXqywNyA4QuE')
TELEGRAM_CHAT_ID = os.environ.get('617879156')

# ==========================================
# PARTIE 1 : LES AGENTS (Ton code d'origine)
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

# ==========================================
# PARTIE 2 : RÉCUPÉRATION DES PRIX
# ==========================================
def recuperer_prix_binance(symbole="BTCUSDT"):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbole}&interval=15m&limit=100"
    try:
        context = ssl._create_unverified_context()
        requete = urllib.request.urlopen(url, timeout=10, context=context)
        donnees = json.loads(requete.read().decode('utf-8'))
        return [float(bougie[4]) for bougie in donnees]
    except Exception:
        return []

def recuperer_prix_yahoo(symbole):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbole}?interval=15m&range=5d"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        context = ssl._create_unverified_context()
        req = urllib.request.Request(url, headers=headers)
        requete = urllib.request.urlopen(req, timeout=10, context=context)
        donnees = json.loads(requete.read().decode('utf-8'))
        resultat = donnees['chart']['result'][0]
        prix = resultat['indicators']['quote'][0]['close']
        return [p for p in prix if p is not None]
    except Exception:
        return []

def chercher_pepites_solana():
    url = "https://api.dexscreener.com/latest/dex/search?q=SOL"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        context = ssl._create_unverified_context()
        req = urllib.request.Request(url, headers=headers)
        requete = urllib.request.urlopen(req, timeout=10, context=context)
        donnees = json.loads(requete.read().decode('utf-8'))
        paires = donnees.get('pairs', [])
        pepites = []
        for paire in paires:
            if paire.get('chainId') != 'solana': continue
            volume_24h = paire.get('volume', {}).get('h24', 0)
            liquidite = paire.get('liquidity', {}).get('usd', 0)
            if volume_24h > 500000 and liquidite > 100000:
                info = paire.get('info', {})
                socials = info.get('socials', [])
                a_un_lien_social = any(s.get('type') in ['twitter', 'telegram'] for s in socials)
                if a_un_lien_social:
                    pepites.append({
                        'nom': paire.get('baseToken', {}).get('symbol', 'INCONNU'),
                        'prix': paire.get('priceUsd', '0'),
                        'volume': volume_24h,
                        'liquidite': liquidite,
                        'change_24h': paire.get('priceChange', {}).get('h24', 0),
                        'url': paire.get('url', ''),
                        'socials': socials
                    })
        pepites.sort(key=lambda x: x['volume'], reverse=True)
        return pepites[:2]
    except Exception:
        return []

# ==========================================
# PARTIE 3 : ENVOI TELEGRAM
# ==========================================
def envoyer_alerte_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Erreur : Token ou Chat ID manquant.")
        return
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
    if not prix or len(prix) < 50: return None
    votes = [agent_trend(prix), agent_rsi(prix), agent_breakout(prix), agent_macd(prix), agent_support_resistance(prix)]
    return {"nom": nom, "prix": prix[-1], "buys": votes.count(1), "sells": votes.count(-1)}

# ==========================================
# PARTIE 4 : LA BOUCLE D'ANALYSE
# ==========================================
def boucle_analyse():
    print("🌍 Bot ULTIME démarré...")
    envoyer_alerte_telegram("🌍 *Bot ULTIME activé !* Je surveille les marchés et les pépites Solana.")
    
    derniers_signaux = {"BTC": "NEUTRE", "GOLD": "NEUTRE", "NASDAQ": "NEUTRE"}
    deja_envoyes_solana = set()
    compteur_minutes = 0

    while True:
        try:
            res_btc = analyser_marche("BTC", recuperer_prix_binance("BTCUSDT"))
            res_gold = analyser_marche("GOLD", recuperer_prix_yahoo("GC=F"))
            res_nasdaq = analyser_marche("NASDAQ", recuperer_prix_yahoo("NQ=F"))
            
            resultats = [r for r in [res_btc, res_gold, res_nasdaq] if r is not None]
            msg_statut = "📊 *Résumé des Marchés*\n\n"
            
            for r in resultats:
                nom = r["nom"]
                emoji = "₿" if nom == "BTC" else "🥇" if nom == "GOLD" else "📈"
                msg_statut += f"{emoji} *{nom}* : {r['prix']:.2f} $ | A:{r['buys']}/5 V:{r['sells']}/5\n"
                
                if r["buys"] >= 4 and derniers_signaux[nom] != "ACHAT":
                    envoyer_alerte_telegram(f"🚨 *CONSENSUS ACHAT (4/5)* sur {nom} {emoji}\nPrix : `{r['prix']:.2f} $`")
                    derniers_signaux[nom] = "ACHAT"
                elif r["sells"] >= 4 and derniers_signaux[nom] != "VENTE":
                    envoyer_alerte_telegram(f"🚨 *CONSENSUS VENTE (4/5)* sur {nom} {emoji}\nPrix : `{r['prix']:.2f} $`")
                    derniers_signaux[nom] = "VENTE"
                elif r["buys"] < 4 and r["sells"] < 4:
                    derniers_signaux[nom] = "NEUTRE"

            compteur_minutes += 1
            if compteur_minutes % 15 == 0:
                envoyer_alerte_telegram(msg_statut)

            if compteur_minutes % 10 == 0:
                pepites = chercher_pepites_solana()
                for token in pepites:
                    if token['nom'] not in deja_envoyes_solana:
                        msg = f"💎 *Pépite Solana Détectée*\n\n"
                        msg += f"🪙 *{token['nom']}*\n💰 Prix : `{token['prix']} $`\n"
                        msg += f"📊 Var 24h : `{token['change_24h']}%`\n"
                        msg += f"💧 Liquidité : `{token['liquidite']:,.0f} $`\n"
                        msg += f"📈 Volume : `{token['volume']:,.0f} $`\n\n"
                        for social in token['socials']:
                            if social.get('type') == 'twitter': msg += f"🐦 [Twitter/X]({social['url']})\n"
                            elif social.get('type') == 'telegram': msg += f"✈️ [Telegram]({social['url']})\n"
                        msg += f"\n🔗 [Voir sur DEX Screener]({token['url']})\n⚠️ *DYOR avant d'investir.*"
                        envoyer_alerte_telegram(msg)
                        deja_envoyes_solana.add(token['nom'])
        except Exception as e:
            print(f"Erreur dans la boucle : {e}")

        time.sleep(60)

# ==========================================
# PARTIE 5 : SERVEUR WEB POUR RENDER
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot d'analyse actif en arrière-plan."

if __name__ == "__main__":
    # On lance l'analyse dans un fil séparé
    t = threading.Thread(target=boucle_analyse)
    t.daemon = True
    t.start()
    
    # On lance le serveur web
    port = int(os.environ.get('PORT', 10000))
    app.run(host="0.0.0.0", port=port)
