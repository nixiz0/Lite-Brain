from CONFIG import LANGUAGE

TRANSLATIONS = {
    "en": {
        # ========== [PYTHON SCRIPTS TRANSLATE] ==========
        # app/markdown_utils
        "think_mode": "🧠 Model Thinking...",

        # app/app.py
        "default_folder_name": "General",
        "welcome_title": "Welcome",
        "welcome_summary": "Welcome Message",
        "welcome_body": (
            "### Welcome to Lite-Brain! 🚀\n\n"
            "Hey there! I'm **Hey Initium**, the creator of this project.\n"
            "Thanks for trying out **Lite-Brain**, a lightweight and fast local AI designed to cover 90% of everyday needs "
            "without relying on huge cloud-based models.\n\n"
            "If you're curious, you can also find me on YouTube:\n"
            "👉 https://www.youtube.com/@Initium0_0\n\n"
            "**What is Lite-Brain?**\n"
            "- A local, efficient and privacy-friendly personal AI.\n"
            "- Runs on mid-range/good PCs, even with a small RTX.\n"
            "- Includes multiple modes (Classic / Turbo / Ultra) depending on your hardware.\n\n"
            "**What can it help you with?**\n"
            "🧠 Writing & rewriting — emails, texts, summaries\n"
            "💬 Document and PDF summarization\n"
            "💡 Idea generation & brainstorming\n"
            "🧩 Coding assistance (small functions, explanations, scripts)\n"
            "📚 Learning & concept explanations\n"
            "🌐 Translation & style adaptation\n"
            "🗂️ Planning and organization\n"
            "⚙️ General conversation & support\n\n"
            "Feel free to type anything to get started !"
        ),

        # app/routes/routes.py
        "fallback_folder_name": "General",
        "new_conversation_title": "New conversation",
        "new_conversation_summary": "New conversation",

        # app/routes/routes_folders.py
        "slug_fallback_folder": "Folder",
        "new_folder_base_name": "New folder",

        "error_folder_not_found": "Folder not found",
        "error_document_not_found": "Document not found",
        "error_name_empty": "The name cannot be empty.",
        "error_name_exists": "A file with that name already exists.",
        "error_empty_conversation_export": "Empty conversation, nothing to export",
        "error_file_not_found_on_server": "File not found on the server",

        "transcript_title_label": "Title",
        "transcript_role_user": "User",
        "transcript_role_assistant": "Assistant",
        "transcript_conversation_fallback_title": "Conversation",

        # app/routes/routes_conversations.py
        "error_title_empty": "The title cannot be empty.",
        "error_full_doc_unavailable": (
            "**Error** It's not possible to analyze the full document at this time..\n\n"
            "> Your message :  \n`{message}`\n"
        ),
        "error_model_unavailable": (
            "**Error** It's not possible to query the model at this time..\n\n"
            "> Your message:  \n`{message}`\n"
        ),
        "error_calling_model": "Error calling the model",
        "rag_no_relevant_info": (
            "After analyzing the document(s), I did not find "
            "relevant information to answer your question."
        ),

        # app/rag/functions/batch_chunk.py
        "full_doc_fallback_title": "Document {doc_id}",
        "full_doc_section_heading": "## {title} (Document ID: {doc_id})\n\n{answer}",

        # app/llm/ll_bootstrap.py
        "bootstrap_no_models_required": "No models required.",
        "bootstrap_checking_models": "Checking installed models...",
        "bootstrap_contact_error": "Could not contact Ollama: {error}",
        "bootstrap_downloading_model": "Downloading {name}...",
        "bootstrap_model_status": "{name}: {status}",
        "bootstrap_model_done": "{name}: done",
        "bootstrap_all_installed": "All required models are already installed.",
        "bootstrap_pull_error": "Error while pulling {model}: {error}",
        "bootstrap_all_downloaded": "All models downloaded.",

        # Universal Error
        "error_conversation_not_found": "Conversation not found",


        # ========== [HTMX SCRIPTS TRANSLATE] ==========
        # templates/base.html
        "app_title": "Lite-Brain",
        "bootstrap_overlay_title": "Preparing your local models…",
        "bootstrap_overlay_default_message": "Checking installed models…",
        "bootstrap_initializing": "Initializing…",
        "bootstrap_overlay_hint": (
            "Models are being downloaded and prepared. This only happens "
            "the first time for each model."
        ),

        "sidebar_open_aria": "Open the sidebar",
        "sidebar_open_title": "Open the sidebar",
        "sidebar_show_aria": "Show sidebar",
        "sidebar_show_title": "Show sidebar",

        # templates/folders/_folder_documents_list.html
        "doc_added_on": "Added on {date}",
        "doc_open": "Open",
        "doc_rename": "Rename",
        "doc_delete": "Delete",
        "doc_delete_confirm": "Delete this document?",
        "doc_none": "No documents are currently in this folder.",

        # templates/folders/_folder_modal.html
        "folder_rename_button": "Rename",
        "folder_delete_button": "Delete",
        "folder_delete_confirm": "Delete this folder and all its documents permanently?",
        "folder_close_aria": "Close",

        "folder_upload_headline": "Drag and drop your files here, or",
        "folder_upload_click_to_select": "click to select",
        "folder_upload_hint": "Up to 5 documents per upload.",
        "folder_upload_loading": "Uploading & indexing the document...",

        # templates/folders/_folders.html
        "folder_docs_count": "%s doc%s",
        "folder_empty_list": "No folders at the moment.",

        # templates/conversations/_conversation_title_edit.html
        "conversation_fallback_title": "Conversation {id}",
        "conversation_rename_save_title": "Save",
        "conversation_rename_save_label": "OK",
        "conversation_rename_cancel_title": "Cancel",
        "conversation_rename_cancel_label": "Cancel",

        # templates/conversations/_conversations.html
        "conversation_fallback_short": "Conv {id}",
        "conversation_title_hint": "Double-click to rename",
        "conversation_rename_title": "Rename",
        "conversation_delete_title": "Delete",
        "conversation_delete_confirm": "Permanently delete « {title} » ?",

        # templates/components/sidebar.html
        "sidebar_nav_aria": "Navigation sidebar",
        "sidebar_app_name": "Lite-Brain",
        "sidebar_collapse_title": "Collapse the sidebar",
        "sidebar_collapse_aria": "Collapse the sidebar",
        "sidebar_close_title": "Close",
        "sidebar_close_aria": "Close the sidebar",
        "sidebar_folders_label": "Folders",
        "sidebar_new_folder_title": "New folder",
        "sidebar_conversations_label": "Conversations",
        "sidebar_new_conversation_title": "New conversation",

        # templates/chat/chat.html
        "llm_tier_default": "Default",
        "llm_tier_turbo": "Turbo",
        "llm_tier_ultra": "Ultra",
        "mode_bar_toggle_title": "Show/hide the mode bar",
        "mode_free_pill": "Free",
        "mode_free_label": "Free mode",
        "mode_free_desc": "Normal, balanced answers.",
        "mode_write_pill": "Write",
        "mode_write_label": "Writing & rewriting",
        "mode_write_desc": "Emails, posts, corrections, style improvements.",
        "mode_docs_pill": "Docs",
        "mode_docs_label": "Docs & PDFs",
        "mode_docs_desc": "Summaries, key points, Q&A from documents.",
        "mode_brainstorm_pill": "Ideas",
        "mode_brainstorm_label": "Ideas & Brainstorm",
        "mode_brainstorm_desc": "Lots of creative ideas, even a bit crazy.",
        "mode_code_pill": "Code",
        "mode_code_label": "Code helper",
        "mode_code_desc": "Explain, fix, and write code snippets.",
        "mode_learn_pill": "Learn",
        "mode_learn_label": "Learn & explain",
        "mode_learn_desc": "Step-by-step explanations, examples, pedagogy.",
        "mode_translate_pill": "Translate",
        "mode_translate_label": "Translate & adapt",
        "mode_translate_desc": "Fast translation and tone/style adaptation.",
        "mode_plan_pill": "Plan",
        "mode_plan_label": "Plan & organize",
        "mode_plan_desc": "To-dos, project structure, action plans.",
        "mode_coaching_pill": "Advice",
        "mode_coaching_label": "Coaching & advice",
        "mode_coaching_desc": "Practical advice and concrete action plans.",
        "mode_wellbeing_pill": "Motivation",
        "mode_wellbeing_label": "Well-being & motivation",
        "mode_wellbeing_desc": "Warm tone, support, motivation.",
        "docs_options_label": "Docs mode :",
        "docs_mode_rag": "Targeted search",
        "docs_mode_full": "Full document",
        "docs_mode_hint": "Targeted = faster / Full = summary & continuous reading",
        "mode_more_title": "Other modes",
        "mode_more_close": "Close",
        "full_doc_progress_title": "Analysis of the document…",
        "source_selector_button_title": "Choose the files and documents used for the response",
        "composer_placeholder": "Write a message...",
        "composer_send": "Send",
        "composer_stop": "Stop",

        # templates/chat/_source_selector_modal.html
        "source_modal_title": "Choose the knowledge to use",
        "source_modal_subtitle": "Select one or more folders and/or documents for this question.",
        "source_modal_close_title": "Close",
        "source_folder_label": "Folder • {count} document{suffix}",
        "source_folder_docs_in_folder": "Documents in this folder",
        "source_modal_empty": "No folders yet. Add documents to the sidebar to use them here.",
        "source_modal_cancel": "Cancel",
        "source_modal_apply": "Apply",

        # templates/chat/_source_selection_summary.html
        "source_summary_clear_title": "Clear source selection",
        "source_summary_label": "Sources :",
        "source_summary_folder_badge": "Folder",
        "source_summary_folder_remove_title": "Remove this folder",
        "source_summary_doc_badge": "Doc",
        "source_summary_doc_remove_title": "Remove this document",

        # templates/chat/_messages.html
        "msg_rag_summary": "See the passages used ({count})",
        "msg_rag_doc_unknown": "Unknown document",
        "msg_rag_chunk_label": "Chunk {index}",


        # ========== [JAVASCRIPT SCRIPTS TRANSLATE] ==========
        # modules/llm-bootstrap.js
        "js_llm_preparing_models": "Preparing models…",
        "js_llm_waiting_server": "Waiting for LLM server to be reachable…",
        "js_llm_connection": "Connection…",

        # modules/ui/dropzone.js
        "js_dropzone_only_first_files": "Only the first {max} files were taken.",
    },




    "fr": {
        # ========== [PYTHON SCRIPTS TRANSLATE] ==========
        # app/markdown_utils
        "think_mode": "🧠 Réflexion du modèle...",

        # app/app.py
        "default_folder_name": "Général",
        "welcome_title": "Bienvenue",
        "welcome_summary": "Message de bienvenue",
        "welcome_body": (
            "### Bienvenue dans Lite-Brain ! 🚀\n\n"
            "Salut ! Je suis **Hey Initium**, le créateur de ce projet.\n"
            "Merci d’essayer **Lite-Brain**, une IA locale légère et rapide pensée pour couvrir 90% des besoins du quotidien "
            "sans dépendre de gros modèles cloud.\n\n"
            "Si tu es curieux, tu peux aussi me trouver sur YouTube :\n"
            "👉 https://www.youtube.com/@Initium0_0\n\n"
            "**C’est quoi Lite-Brain ?**\n"
            "- Une IA personnelle locale, efficace et respectueuse de ta vie privée.\n"
            "- Tourne sur des PC moyens / bons, même avec une petite RTX.\n"
            "- Propose plusieurs modes (Classique / Turbo / Ultra) selon ton matériel.\n\n"
            "**En quoi ça peut t’aider ?**\n"
            "🧠 Rédaction & réécriture — mails, textes, résumés\n"
            "💬 Résumés de documents et PDF\n"
            "💡 Génération d’idées & brainstorming\n"
            "🧩 Aide au code (petites fonctions, explications, scripts)\n"
            "📚 Apprentissage & explication de concepts\n"
            "🌐 Traduction & adaptation de style\n"
            "🗂️ Organisation & planification\n"
            "⚙️ Conversation générale & support\n\n"
            "N’hésite pas à taper quoi que ce soit pour commencer !"
        ),

        # app/routes/routes.py
        "fallback_folder_name": "Général",
        "new_conversation_title": "Nouvelle conversation",
        "new_conversation_summary": "Nouvelle conversation",


        # app/routes/routes_folders.py
        "slug_fallback_folder": "Dossier",
        "new_folder_base_name": "Nouveau dossier",

        "error_folder_not_found": "Dossier introuvable",
        "error_document_not_found": "Document introuvable",
        "error_name_empty": "Le nom ne peut pas être vide.",
        "error_name_exists": "Un fichier avec ce nom existe déjà.",
        "error_empty_conversation_export": "Conversation vide, rien à exporter",
        "error_file_not_found_on_server": "Fichier introuvable sur le serveur",

        "transcript_title_label": "Titre",
        "transcript_role_user": "Utilisateur",
        "transcript_role_assistant": "Assistant",
        "transcript_conversation_fallback_title": "Conversation",

        # app/routes/routes_conversations.py
        "error_title_empty": "Le titre ne peut pas être vide.",
        "error_full_doc_unavailable": (
            "**Erreur** Impossible d'analyser le document complet pour le moment.\n\n"
            "> Ton message :  \n`{message}`\n"
        ),
        "error_model_unavailable": (
            "**Erreur** Impossible d'interroger le modèle pour le moment.\n\n"
            "> Ton message :  \n`{message}`\n"
        ),
        "error_calling_model": "Erreur lors de l'appel au modèle",
        "rag_no_relevant_info": (
            "Après analyse du(des) document(s), je n'ai pas trouvé "
            "d'information pertinente pour répondre à ta question."
        ),

        # app/rag/functions/batch_chunk.py
        "full_doc_fallback_title": "Document {doc_id}",
        "full_doc_section_heading": "## {title} (ID du document : {doc_id})\n\n{answer}",

        # app/llm/ll_bootstrap.py
        "bootstrap_no_models_required": "Aucun modèle requis.",
        "bootstrap_checking_models": "Vérification des modèles installés...",
        "bootstrap_contact_error": "Impossible de contacter Ollama : {error}",
        "bootstrap_downloading_model": "Téléchargement de {name}...",
        "bootstrap_model_status": "{name} : {status}",
        "bootstrap_model_done": "{name} : terminé",
        "bootstrap_all_installed": "Tous les modèles requis sont déjà installés.",
        "bootstrap_pull_error": "Erreur lors du téléchargement de {model} : {error}",
        "bootstrap_all_downloaded": "Tous les modèles ont été téléchargés.",

        # Universal Error
        "error_conversation_not_found": "Conversation introuvable",


        # ========== [HTMX SCRIPTS TRANSLATE] ==========
        # templates/base.html
        "app_title": "Lite-Brain",
        "bootstrap_overlay_title": "Préparation de vos modèles locaux…",
        "bootstrap_overlay_default_message": "Vérification des modèles installés…",
        "bootstrap_initializing": "Initialisation…",
        "bootstrap_overlay_hint": (
            "Les modèles sont en cours de téléchargement et de préparation. "
            "Cela ne se produit que la première fois pour chaque modèle."
        ),

        "sidebar_open_aria": "Ouvrir la barre latérale",
        "sidebar_open_title": "Ouvrir la barre latérale",
        "sidebar_show_aria": "Afficher la barre latérale",
        "sidebar_show_title": "Afficher la barre latérale",

        # templates/folders/_folder_documents_list.html
        "doc_added_on": "Ajouté le {date}",
        "doc_open": "Ouvrir",
        "doc_rename": "Renommer",
        "doc_delete": "Supprimer",
        "doc_delete_confirm": "Supprimer ce document ?",
        "doc_none": "Aucun document dans ce dossier pour le moment.",

        # templates/folders/_folder_modal.html
        "folder_rename_button": "Renommer",
        "folder_delete_button": "Supprimer",
        "folder_delete_confirm": "Supprimer ce dossier et tous ses documents définitivement ?",
        "folder_close_aria": "Fermer",

        "folder_upload_headline": "Glissez-déposez vos fichiers ici, ou",
        "folder_upload_click_to_select": "cliquez pour sélectionner",
        "folder_upload_hint": "Jusqu'à 5 documents par envoi.",
        "folder_upload_loading": "Chargement et indexation du document...",

        # templates/folders/_folders.html
        "folder_docs_count": "%s document%s",
        "folder_empty_list": "Aucun dossier pour le moment.",

        # templates/conversations/_conversation_title_edit.html
        "conversation_fallback_title": "Conversation {id}",
        "conversation_rename_save_title": "Enregistrer",
        "conversation_rename_save_label": "OK",
        "conversation_rename_cancel_title": "Annuler",
        "conversation_rename_cancel_label": "Annuler",

        # templates/conversations/_conversations.html
        "conversation_fallback_short": "Conv {id}",
        "conversation_title_hint": "Double-clique pour renommer",
        "conversation_rename_title": "Renommer",
        "conversation_delete_title": "Supprimer",
        "conversation_delete_confirm": "Supprimer définitivement « {title} » ?",

        # templates/components/sidebar.html
        "sidebar_nav_aria": "Barre latérale de navigation",
        "sidebar_app_name": "Lite-Brain",
        "sidebar_collapse_title": "Replier la barre latérale",
        "sidebar_collapse_aria": "Replier la barre latérale",
        "sidebar_close_title": "Fermer",
        "sidebar_close_aria": "Fermer la barre latérale",
        "sidebar_folders_label": "Dossiers",
        "sidebar_new_folder_title": "Nouveau dossier",
        "sidebar_conversations_label": "Conversations",
        "sidebar_new_conversation_title": "Nouvelle conversation",

        # templates/chat/chat.html
        "llm_tier_default": "Par défaut",
        "llm_tier_turbo": "Turbo",
        "llm_tier_ultra": "Ultra",
        "mode_bar_toggle_title": "Afficher/masquer la barre de modes",
        "mode_free_pill": "Libre",
        "mode_free_label": "Mode libre",
        "mode_free_desc": "Réponses normales et équilibrées.",
        "mode_write_pill": "Écriture",
        "mode_write_label": "Écriture & réécriture",
        "mode_write_desc": "Emails, posts, corrections, amélioration du style.",
        "mode_docs_pill": "Docs",
        "mode_docs_label": "Docs & PDFs",
        "mode_docs_desc": "Résumés, points clés, questions/réponses à partir de documents.",
        "mode_brainstorm_pill": "Idées",
        "mode_brainstorm_label": "Idées & Brainstorm",
        "mode_brainstorm_desc": "Beaucoup d'idées créatives, parfois un peu folles.",
        "mode_code_pill": "Code",
        "mode_code_label": "Aide au code",
        "mode_code_desc": "Expliquer, corriger et écrire des extraits de code.",
        "mode_learn_pill": "Apprendre",
        "mode_learn_label": "Apprendre & expliquer",
        "mode_learn_desc": "Explications pas à pas, exemples, pédagogie.",
        "mode_translate_pill": "Traduire",
        "mode_translate_label": "Traduire & adapter",
        "mode_translate_desc": "Traduction rapide et adaptation de ton/style.",
        "mode_plan_pill": "Planifier",
        "mode_plan_label": "Planifier & organiser",
        "mode_plan_desc": "To-do lists, structure de projets, plans d'action.",
        "mode_coaching_pill": "Conseils",
        "mode_coaching_label": "Coaching & conseils",
        "mode_coaching_desc": "Conseils concrets et plans d'action pratiques.",
        "mode_wellbeing_pill": "Motivation",
        "mode_wellbeing_label": "Bien-être & motivation",
        "mode_wellbeing_desc": "Ton chaleureux, soutien, motivation.",
        "docs_options_label": "Mode Docs :",
        "docs_mode_rag": "Recherche ciblée",
        "docs_mode_full": "Document complet",
        "docs_mode_hint": "Ciblé = plus rapide / Complet = résumé & lecture continue",
        "mode_more_title": "Autres modes",
        "mode_more_close": "Fermer",
        "full_doc_progress_title": "Analyse du document…",
        "source_selector_button_title": "Choisir les dossiers et documents utilisés pour la réponse",
        "composer_placeholder": "Écrire un message...",
        "composer_send": "Envoyer",
        "composer_stop": "Arrêter",

        # templates/chat/_source_selector_modal.html
        "source_modal_title": "Choisissez les connaissances à utiliser",
        "source_modal_subtitle": "Sélectionnez un ou plusieurs dossiers et/ou documents pour cette question.",
        "source_modal_close_title": "Fermer",
        "source_folder_label": "Dossier • {count} document{suffix}",
        "source_folder_docs_in_folder": "Documents dans ce dossier",
        "source_modal_empty": "Aucun dossier pour le moment. Ajoutez des documents dans la barre latérale pour les utiliser ici.",
        "source_modal_cancel": "Annuler",
        "source_modal_apply": "Appliquer",

        # templates/chat/_source_selection_summary.html
        "source_summary_clear_title": "Effacer la sélection de sources",
        "source_summary_label": "Sources :",
        "source_summary_folder_badge": "Dossier",
        "source_summary_folder_remove_title": "Retirer ce dossier",
        "source_summary_doc_badge": "Doc",
        "source_summary_doc_remove_title": "Retirer ce document",

        # templates/chat/_messages.html
        "msg_rag_summary": "Voir les passages utilisés ({count})",
        "msg_rag_doc_unknown": "Document inconnu",
        "msg_rag_chunk_label": "Bloc {index}",


        # ========== [JAVASCRIPT SCRIPTS TRANSLATE] ==========
        # modules/llm-bootstrap.js
        "js_llm_preparing_models": "Préparation des modèles…",
        "js_llm_waiting_server": "En attente que le serveur LLM soit joignable…",
        "js_llm_connection": "Connexion…",
        
        # modules/ui/dropzone.js
        "js_dropzone_only_first_files": "Seuls les {max} premiers fichiers ont été pris en compte.",
    },
}


# Catalog for the JS
JS_KEYS = [
    "js_llm_preparing_models",
    "js_llm_waiting_server",
    "js_llm_connection",
    "js_dropzone_only_first_files",
    # You add here all the keys used in the JS
]

def t(key: str) -> str:
    """
    A global helper to retrieve a translated string.
    If the key doesn't exist, the key itself is returned (prevents crashes).
    """
    lang = LANGUAGE
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)

def get_js_catalog(lang: str | None = None) -> dict[str, str]:
    """
    Returns a dictionary {key: translated_string} for JS scripts.
    We only return the keys necessary for the front end, to keep things lightweight.
    """
    lang = lang or LANGUAGE
    catalog = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    return {key: catalog.get(key, key) for key in JS_KEYS}
