import os
import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

PANIC_DB = {
    "0x20": {"models": "Tous iPhones", "panne": "Problème batterie / PMIC", "solution": "Vérifier/remplacer la batterie. Si le problème persiste, tester le PMIC (puce de gestion d'alimentation)."},
    "0x40": {"models": "Tous iPhones", "panne": "Court-circuit sur la ligne d'alimentation", "solution": "Inspecter la carte mère pour un court-circuit, vérifier les bobines et condensateurs autour du PMIC."},
    "0x41": {"models": "Tous iPhones", "panne": "Problème d'alimentation CPU / SoC", "solution": "Vérifier les rails d'alimentation du SoC. Peut nécessiter un rebillage ou remplacement du PMIC."},
    "0xa9": {"models": "Tous iPhones", "panne": "Erreur de démarrage du CPU (watchdog timeout)", "solution": "Souvent lié à une corruption NAND ou un problème de mémoire. Tenter une restauration DFU."},
    "0x4000": {"models": "Tous iPhones", "panne": "Problème de connectivité interne (bus SPI/I2C)", "solution": "Vérifier les connecteurs FPC et les nappes. Nettoyer les contacts à l'IPA."},
    "mic1": {"models": "iPhone 12 et antérieurs", "panne": "Panne du microphone principal (micro du bas)", "solution": "Remplacer le microphone du bas ou le module dock. Vérifier la nappe de connexion."},
    "mic2": {"models": "iPhone 12 et antérieurs", "panne": "Panne du microphone secondaire (micro du haut / AirHoles)", "solution": "Remplacer le microphone supérieur. Vérifier l'absence d'humidité sur la nappe."},
    "prs0": {"models": "iPhone 12 et antérieurs", "panne": "Capteur de pression / baromètre défaillant", "solution": "Remplacer le capteur de pression. Vérifier les points de soudure sur la carte mère."},
    "tg0b": {"models": "iPhone 12 et antérieurs", "panne": "Problème Touch ID / bouton Home", "solution": "Vérifier la nappe du Touch ID. Attention : le Touch ID est jumelé à la carte mère, il ne peut pas être remplacé par un tiers."},
    "ans2": {"models": "iPhone 12 et antérieurs", "panne": "Contrôleur NAND / stockage flash défaillant", "solution": "Problème de stockage sérieux. Tenter une restauration DFU. Si échec, remplacement ou rebillage de la puce NAND nécessaire."},
    "0x800": {"models": "iPhone 13", "panne": "Panne caméra avant (TrueDepth / Face ID)", "solution": "Vérifier la nappe FPC de la caméra avant. Remplacer le module caméra avant si nécessaire."},
    "0x1000": {"models": "iPhone 13", "panne": "Panne caméra arrière principale", "solution": "Vérifier le connecteur de la caméra arrière. Remplacer le module caméra arrière."},
    "0x1800": {"models": "iPhone 13", "panne": "Panne du module LiDAR / capteur de proximité", "solution": "Remplacer le module LiDAR ou le capteur de proximité selon le modèle."},
    "0x400": {"models": "iPhone 13", "panne": "Problème audio / codec audio", "solution": "Vérifier le circuit audio (Cirrus Logic). Inspecter les points de soudure du codec audio sur la carte mère."},
    "0x400000": {"models": "iPhone 14", "panne": "Panne batterie / contrôleur de charge", "solution": "Remplacer la batterie. Si le problème persiste, vérifier le contrôleur de charge (U2/Tristar)."},
    "0x100000": {"models": "iPhone 14", "panne": "Panne module Wi-Fi / Bluetooth", "solution": "Vérifier les antennes Wi-Fi/BT. Remplacer le module sans fil ou le rebraser sur la carte."},
    "0x500000": {"models": "iPhone 14", "panne": "Problème écran / contrôleur d'affichage", "solution": "Tester avec un autre écran. Si résolu, remplacer l'écran. Sinon, inspecter le contrôleur d'affichage."},
    "0x200000": {"models": "iPhone 14", "panne": "Problème capteur biométrique (Face ID)", "solution": "Le Face ID est jumelé. Vérifier la nappe du module TrueDepth. Un remplacement tiers ne restaure pas Face ID."},
    "0x80000": {"models": "iPhone 14 Pro / Pro Max", "panne": "Panne caméra périscopique / téléobjectif", "solution": "Remplacer le module caméra téléobjectif. Vérifier le connecteur et la nappe FPC."},
    "0x40000": {"models": "iPhone 14 Pro / Pro Max", "panne": "Problème Always-On Display / écran ProMotion", "solution": "Vérifier la nappe de l'écran et les connecteurs. Remplacer l'écran OLED si nécessaire."},
    "0x10000": {"models": "iPhone 14 Pro / Pro Max", "panne": "Problème Dynamic Island / capteurs TrueDepth", "solution": "Vérifier les composants du Dynamic Island. Le module Face ID est jumelé et ne peut être remplacé par un tiers."},
    "0x20000": {"models": "iPhone 14 Pro / Pro Max", "panne": "Panne LiDAR Scanner", "solution": "Remplacer le module LiDAR. Vérifier les connexions FPC du module arrière."},
    "0x200000_15": {"models": "iPhone 15", "panne": "Problème port USB-C / contrôleur de charge", "solution": "Vérifier/nettoyer le port USB-C. Remplacer le module de charge. Vérifier le PMIC de charge."},
    "0x80000_15": {"models": "iPhone 15", "panne": "Problème connectivité cellulaire / modem", "solution": "Vérifier la SIM et les antennes. Un problème persistant indique une panne du modem (Qualcomm) sur la carte mère."},
    "0x100000_15": {"models": "iPhone 15", "panne": "Panne caméra arrière 48 MP", "solution": "Remplacer le module caméra arrière principal. Vérifier la nappe FPC."},
    "0xa1": {"models": "iPhone 15 Pro / Pro Max", "panne": "Problème thermique / surchauffe SoC A17 Pro", "solution": "Vérifier la chambre à vapeur (vapeur cooling). Nettoyer les grilles. Si persistant, problème de pâte thermique ou SoC."},
    "0x300000": {"models": "iPhone 15 Pro / Pro Max", "panne": "Panne bouton Action", "solution": "Vérifier la nappe du bouton Action. Remplacer le module bouton latéral si défaillant."},
    "0x400000_15p": {"models": "iPhone 15 Pro / Pro Max", "panne": "Problème cadre en titane / antennes", "solution": "Vérifier les antennes intégrées au cadre titane. Inspecter les connexions RF sur la carte mère."},
    "0x700000": {"models": "iPhone 15 Pro / Pro Max", "panne": "Panne caméra tériscopique (5x zoom)", "solution": "Remplacer le module caméra tériscopique. Vérifier la nappe FPC dédiée."},
}

PANIC_ALIASES = {
    "0x200000": ["0x200000", "0x200000_15"],
    "0x80000": ["0x80000", "0x80000_15"],
    "0x100000": ["0x100000", "0x100000_15"],
    "0x400000": ["0x400000", "0x400000_15p"],
}

IPHONE_MODELS = [
    "iPhone 12 et antérieurs",
    "iPhone 13",
    "iPhone 14",
    "iPhone 14 Pro / Pro Max",
    "iPhone 15",
    "iPhone 15 Pro / Pro Max",
]

SELECT_MODEL, ENTER_CODE = range(2)

def lookup_code(code, model=None):
    code_lower = code.lower().strip()
    results = []
    keys_to_check = PANIC_ALIASES.get(code_lower, [code_lower])
    for key in keys_to_check:
        if key in PANIC_DB:
            entry = PANIC_DB[key]
            if model is None or model.lower() in entry["models"].lower():
                results.append(entry)
    if not results and model:
        for key in keys_to_check:
            if key in PANIC_DB:
                results.append(PANIC_DB[key])
    return results


def extract_codes_from_log(log_text):
    import re
    found = set()
    hex_pattern = re.compile(r'\b(0x[0-9a-fA-F]+)\b')
    for match in hex_pattern.finditer(log_text):
        found.add(match.group(1).lower())
    for key in PANIC_DB:
        clean_key = re.sub(r'_\w+$', '', key)
        if re.search(r'\b' + re.escape(clean_key) + r'\b', log_text, re.IGNORECASE):
            found.add(clean_key)
    return list(found)


def format_diagnostic(code, entry):
    return (
        f"\U0001f50d *Code :* `{code.upper()}`\n"
        f"\U0001f4f1 *Modèles :* {entry['models']}\n"
        f"\u26a0\ufe0f *Panne :* {entry['panne']}\n"
        f"\U0001f527 *Solution :* {entry['solution']}"
    )


async def start(update, context):
    await update.message.reply_text(
        "\U0001f44b *Bienvenue sur le bot de diagnostic Panic Log iPhone !*\n\n"
        "Ce bot analyse les codes d'erreur présents dans les logs de panique (panic log) "
        "de votre iPhone et vous donne la panne probable et la solution.\n\n"
        "\U0001f4cb *Commandes disponibles :*\n"
        "\u2022 /analyse \u2014 Analyser un code panic manuellement\n"
        "\u2022 /log \u2014 Coller un panic-full complet pour extraction automatique\n"
        "\u2022 /codes \u2014 Voir tous les codes supportés\n"
        "\u2022 /tuto \u2014 Comment trouver le panic log sur votre iPhone\n\n"
        "\U0001f6e0\ufe0f Source des données : repair.wiki",
        parse_mode="Markdown",
    )


async def analyse_start(update, context):
    keyboard = [
        [InlineKeyboardButton(model, callback_data=f"model:{model}")]
        for model in IPHONE_MODELS
    ]
    await update.message.reply_text(
        "\U0001f4f1 *Choisissez votre modèle iPhone :*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return SELECT_MODEL


async def model_selected(update, context):
    query = update.callback_query
    await query.answer()
    model = query.data.replace("model:", "")
    context.user_data["selected_model"] = model
    await query.edit_message_text(
        f"\u2705 Modèle sélectionné : *{model}*\n\n"
        "\U0001f522 Entrez maintenant le code panic (ex: `mic1`, `0x800`, `0x1000`) :",
        parse_mode="Markdown",
    )
    return ENTER_CODE


async def code_received(update, context):
    code = update.message.text.strip()
    model = context.user_data.get("selected_model")
    results = lookup_code(code, model)
    if not results:
        await update.message.reply_text(
            f"\u274c Code `{code}` non reconnu pour ce modèle.\n"
            "Vérifiez l'orthographe ou utilisez /codes pour voir la liste complète.",
            parse_mode="Markdown",
        )
    else:
        for entry in results:
            await update.message.reply_text(format_diagnostic(code, entry), parse_mode="Markdown")
    await update.message.reply_text("Entrez un autre code ou /start pour revenir au menu.")
    return ENTER_CODE


async def analyse_cancel(update, context):
    await update.message.reply_text("\u274c Analyse annulée. Tapez /start pour recommencer.")
    return ConversationHandler.END


async def log_command(update, context):
    await update.message.reply_text(
        "\U0001f4cb *Copiez-collez votre panic-full log ci-dessous :*\n\n"
        "_Le bot extraira automatiquement tous les codes et vous donnera les diagnostics._",
        parse_mode="Markdown",
    )
    context.user_data["awaiting_log"] = True


async def log_text_received(update, context):
    if not context.user_data.get("awaiting_log"):
        return
    log_text = update.message.text
    context.user_data["awaiting_log"] = False
    codes = extract_codes_from_log(log_text)
    if not codes:
        await update.message.reply_text(
            "\U0001f50d Aucun code panic reconnu dans ce log.\n"
            "Assurez-vous de coller le contenu complet du fichier panic-full."
        )
        return
    await update.message.reply_text(
        f"\U0001f50e *{len(codes)} code(s) détecté(s) :* `{'\u0060, \u0060'.join(c.upper() for c in codes)}`\n\nAnalyse en cours...",
        parse_mode="Markdown",
    )
    found_any = False
    for code in codes:
        results = lookup_code(code)
        if results:
            found_any = True
            for entry in results:
                await update.message.reply_text(format_diagnostic(code, entry), parse_mode="Markdown")
    if not found_any:
        await update.message.reply_text(
            "\u26a0\ufe0f Les codes détectés ne sont pas dans la base de données.\n"
            "Utilisez /codes pour voir les codes supportés."
        )

async def codes_command(update, context):
    sections = {
        "\U0001f310 Codes universels (tous iPhones)": ["0x20", "0x40", "0x41", "0xa9", "0x4000"],
        "\U0001f4f1 iPhone 12 et antérieurs": ["mic1", "mic2", "prs0", "tg0b", "ans2"],
        "\U0001f4f1 iPhone 13": ["0x800", "0x1000", "0x1800", "0x400"],
        "\U0001f4f1 iPhone 14": ["0x400000", "0x100000", "0x500000", "0x200000"],
        "\U0001f4f1 iPhone 14 Pro / Pro Max": ["0x80000", "0x40000", "0x10000", "0x20000"],
        "\U0001f4f1 iPhone 15": ["0x200000", "0x80000", "0x100000"],
        "\U0001f4f1 iPhone 15 Pro / Pro Max": ["0xa1", "0x300000", "0x400000", "0x700000"],
    }
    msg = "\U0001f4da *Codes panic supportés :*\n\n"
    for section, codes in sections.items():
        msg += f"*{section}*\n"
        for code in codes:
            import re
            key = code.lower()
            entry = PANIC_DB.get(key)
            if not entry:
                for k, v in PANIC_DB.items():
                    if re.sub(r'_\w+$', '', k) == key:
                        entry = v
                        break
            panne = entry["panne"] if entry else "—"
            msg += f"  \u2022 `{code.upper()}` \u2014 {panne}\n"
        msg += "\n"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def tuto_command(update, context):
    await update.message.reply_text(
        "\U0001f4d6 *Comment trouver le Panic Log sur iPhone*\n\n"
        "*Méthode 1 — Directement sur l'iPhone :*\n"
        "1. Ouvrir *Réglages*\n"
        "2. Aller dans *Confidentialité et sécurité*\n"
        "3. Appuyer sur *Analyse et améliorations*\n"
        "4. Choisir *Données d'analyse*\n"
        "5. Rechercher un fichier commençant par `panic-full-` suivi de la date\n"
        "6. Appuyer dessus \u2192 le fichier texte s'ouvre\n"
        "7. Copier tout le contenu et envoyez-le avec /log\n\n"
        "*Méthode 2 — Via Mac (Console) :*\n"
        "1. Connecter l'iPhone au Mac\n"
        "2. Ouvrir l'app *Console* (dans Applications > Utilitaires)\n"
        "3. Sélectionner l'iPhone dans la barre latérale\n"
        "4. Cliquer sur *Rapports d'erreurs*\n"
        "5. Chercher les fichiers `panic-full-*`\n\n"
        "*Méthode 3 — Via Finder :*\n"
        "1. Connecter l'iPhone au Mac\n"
        "2. Ouvrir Finder \u2192 sélectionner l'iPhone\n"
        "3. Aller dans *Gérer* \u2192 *Fichiers*\n"
        "4. Les logs se trouvent dans le dossier `CrashReporter`\n\n"
        "\U0001f4a1 Une fois le log récupéré, utilisez /log pour l'analyser !",
        parse_mode="Markdown",
    )


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    analyse_conv = ConversationHandler(
        entry_points=[CommandHandler("analyse", analyse_start)],
        states={
            SELECT_MODEL: [CallbackQueryHandler(model_selected, pattern=r"^model:")],
            ENTER_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, code_received)],
        },
        fallbacks=[CommandHandler("start", analyse_cancel)],
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(analyse_conv)
    app.add_handler(CommandHandler("log", log_command))
    app.add_handler(CommandHandler("codes", codes_command))
    app.add_handler(CommandHandler("tuto", tuto_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, log_text_received))
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
    PORT = int(os.environ.get("PORT", 8080))
    if WEBHOOK_URL:
        logger.info(f"Bot démarré en mode webhook sur port {PORT}...")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}",
        )
    else:
        logger.info("Bot démarré en mode polling...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
