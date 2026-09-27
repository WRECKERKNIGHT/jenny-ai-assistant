"""Truthful capability registry for JENNY.

Why this file exists
--------------------
The request was to "add all these skills". Adding ~800 name->phrase mappings
with nothing behind them would recreate the exact false-success bug found in
the audit (see server.py:4092-4094, where an uninstalled app still reports
success). So instead of inflating the alias catalog, every requested capability
is recorded here against its REAL backing, and JENNY reports the gap instead of
hiding it.

Status codes
------------
W:<executor>  works now, deterministic executor named
P:<executor>  partially works, executor named (narrower than requested)
M             genuinely handled by the Groq model in conversation
              (real, but generative -- not a deterministic action)
C:<what>      needs a credential we do not have (API key / account / login)
S:<what>      needs hardware, an external service, or an integration that
              does not exist on this machine
N             not implemented, and nothing pretends otherwise

Nothing in this file invents a capability. `summary()` is what /api/capabilities
reports, and it is expected to show large N/S/C counts -- that is the truth.
"""

from __future__ import annotations

#: Real executors discovered in the codebase, with what they actually do.
EXECUTORS = {
    "pc_actions.open_app": "launch a detected, installed app",
    "pc_actions.close_window": "close the focused window",
    "pc_actions.browser_open": "open a URL in the default browser",
    "pc_actions.browser_search": "search the web in the browser",
    "pc_actions.browser_new_tab": "open a new browser tab",
    "pc_actions.browser_close_tab": "close the active tab",
    "pc_actions.browser_back": "browser back",
    "pc_actions.browser_forward": "browser forward",
    "pc_actions.browser_refresh": "reload the page",
    "pc_actions.browser_new_window": "open a new browser window",
    "pc_actions.browser_reopen_tab": "reopen a closed tab",
    "pc_actions.browser_fullscreen": "toggle browser fullscreen",
    "pc_actions.browser_youtube": "open YouTube",
    "pc_actions.browser_gmail": "open Gmail",
    "pc_actions.browser_github": "open GitHub",
    "pc_actions.volume_up": "raise system volume",
    "pc_actions.volume_down": "lower system volume",
    "pc_actions.volume_mute": "toggle mute",
    "pc_actions.media_play_pause": "media key play/pause",
    "pc_actions.media_next": "media key next track",
    "pc_actions.media_prev": "media key previous track",
    "pc_actions.screenshot": "capture the screen to a file",
    "pc_actions.task_manager": "open Task Manager",
    "pc_actions.show_desktop": "minimise everything (show desktop)",
    "pc_actions.lock_pc": "lock the workstation",
    "pc_actions.lock_screen_timer": "lock after a short countdown",
    "pc_actions.clipboard_read": "read the Windows clipboard (control: clipboard-read)",
    "pc_actions.clipboard_write": "write text to the Windows clipboard (control: clipboard-write)",
    "pc_actions.file_search": "recursive filename search in Desktop/Documents/Downloads (control: file-search)",
    "pc_actions.recent_files": "list recently opened files (control: recent-files)",
    "pc_actions.large_files": "find the largest files in a folder (control: large-files)",
    "pc_actions.list_processes": "list running processes with memory use",
    "pc_actions.startup_apps": "list configured startup entries (control: startup-apps)",
    "pc_actions.system_diagnostics": "battery/cpu/ram/disk/network snapshot (control: system-diagnostics)",
    "app_integrations.focus_window": "focus a window by title substring",
    "app_integrations.foreground_window": "name the foreground window",
    "app_integrations.list_open_apps": "enumerate open windows",
    "app_integrations.app_volume": "per-app volume read/set",
    "app_integrations.list_app_volumes": "list per-app volumes",
    "app_integrations.spotify_action": "Spotify media-key transport",
    "app_integrations.spotify_search_play": "desktop Spotify search and play",
    "spotify_api.queue": "real Spotify queue (Web API, Premium)",
    "spotify_api.playlists": "real Spotify playlists (Web API, Premium)",
    "spotify_api.play_playlist": "start a Spotify playlist (Web API, Premium)",
    "spotify_api.search_and_play": "Spotify search and play (Web API)",
    "hermes_bridge.skills": "list 72 installed Hermes skills",
    "hermes_bridge.memory": "read/append Hermes MEMORY.md and USER.md",
    "hermes_bridge.slack_manifest": "generate the Hermes Slack app manifest",
    "hermes_bridge.memory_provider_status": "memory provider status incl. Honcho",
    "email_integration": "Outlook/Mailbox mail read and send",
    "agency_client": "Agency OS mission state and outreach",
    "tunnel_remote": "Cloudflare quick tunnel for the phone link",
    "server.vault_save": "local memory vault (remember X)",
    "server.system_status": "live battery/cpu/disk/net/ram metrics",
    "server.proactive": "proactive suggestion engine",
    "speech_stt": "speech-to-text and wake word",
    "tts_engine": "Edge TTS speech synthesis",
    "gesture_controller": " webcam gesture control",
    "chrome_bridge": "browser tab and page control",
}

_CATEGORIES = {
    "Advanced Intelligence & Reasoning": {
        "Deep reasoning": "M", "Multi-step planning": "M", "Goal decomposition": "M",
        "Decision-tree generation": "M", "Constraint solving": "M",
        "Pattern recognition": "M", "Anomaly detection": "M", "Deduction": "M",
        "Inductive reasoning": "M", "Hypothesis generation": "M",
        "Hypothesis testing": "M", "Scenario analysis": "M", "What-if analysis": "M",
        "Root-cause analysis": "M", "Tradeoff analysis": "M", "Risk analysis": "M",
        "Dependency analysis": "M", "Priority optimization": "M",
        "Resource allocation": "M", "Strategy generation": "M",
        "Counterargument generation": "M", "Assumption detection": "M",
        "Contradiction detection": "M", "Consistency checking": "M",
        "Confidence estimation": "M", "Uncertainty analysis": "M",
        "Decision support": "M", "Goal tracking": "S:no goal store wired",
        "Long-term planning": "S:no persistent planning store",
        "Autonomous task decomposition": "M",
    },
    "Personal Intelligence": {
        "User preference learning": "P:server.vault_save",
        "Habit recognition": "N", "Routine detection": "N", "Context awareness": "P:server.proactive",
        "Conversation continuity": "P:server.sessions", "Personal knowledge graph": "N",
        "Relationship graph": "N", "Project memory": "P:hermes_bridge.memory",
        "Preference memory": "P:server.vault_save", "Important-date memory": "N",
        "Contextual reminders": "P:server.proactive", "Proactive suggestions": "W:server.proactive",
        "Personalized recommendations": "M", "Personal dashboard": "W:public Agency OS",
        "Daily briefing": "S:no scheduled morning brief", "Weekly briefing": "N",
        "Monthly review": "N", "Goal monitoring": "N", "Habit tracking": "N",
        "Personal analytics": "N",
    },
    "Computer Control": {
        "Launch applications": "W:pc_actions.open_app", "Close applications": "W:pc_actions.close_window",
        "Switch windows": "W:app_integrations.focus_window",
        "Minimize/maximize windows": "P:pc_actions.show_desktop",
        "Window positioning": "N", "Multi-monitor control": "N",
        "Screenshot capture": "W:pc_actions.screenshot", "Screen analysis": "M",
        "OCR": "S:no OCR engine installed (Tesseract/WinRT not wired)",
        "Clipboard management": "W:pc_actions.clipboard_read+clipboard_write",
        "Keyboard automation": "P:pc_actions hotkeys only",
        "Mouse automation": "P:pyautogui in spotify fallback only",
        "File drag/drop automation": "N", "Desktop search": "P:pc_actions.browser_search",
        "Application search": "W:pc_actions.open_app", "Process monitoring": "W:pc_actions.list_processes",
        "CPU monitoring": "W:pc_actions.system_diagnostics",
        "RAM monitoring": "W:pc_actions.system_diagnostics",
        "GPU monitoring": "N", "Disk monitoring": "W:pc_actions.system_diagnostics",
        "Network monitoring": "W:pc_actions.system_diagnostics",
        "Battery monitoring": "W:pc_actions.system_diagnostics",
        "Device information": "W:pc_actions.system_diagnostics",
        "System diagnostics": "W:pc_actions.system_diagnostics",
        "Startup application management": "P:pc_actions.startup_apps (read-only)",
    },
    "File Intelligence": {
        "File search": "W:pc_actions.file_search", "Semantic file search": "N",
        "Duplicate detection": "N", "File classification": "N",
        "Automatic folder organization": "N", "File renaming": "N", "Batch renaming": "N",
        "File tagging": "N", "File metadata extraction": "M",
        "PDF extraction": "S:no PDF library installed",
        "PDF summarization": "S:needs PDF extraction first",
        "PDF comparison": "N", "PDF merging": "N", "PDF splitting": "N",
        "PDF conversion": "N", "Document conversion": "N", "Image-to-text": "N",
        "Document-to-markdown": "N", "Archive management": "N", "Backup management": "N",
        "File cleanup suggestions": "P:pc_actions.large_files",
        "Large-file detection": "W:pc_actions.large_files",
        "Recent-file intelligence": "W:pc_actions.recent_files",
        "Project-folder analysis": "M", "File version comparison": "N",
    },
    "Browser & Web Agent": {
        "Web search": "W:pc_actions.browser_search", "Deep research": "M",
        "Website summarization": "M", "Page extraction": "P:chrome_bridge",
        "Multi-page research": "M", "Source comparison": "M", "Fact verification": "M",
        "Citation collection": "N", "Website monitoring": "S:no scheduler for it",
        "Price monitoring": "S:no retailer accounts", "Product monitoring": "S:no retailer accounts",
        "News monitoring": "P:server /api/news (live RSS)",
        "Form filling": "P:chrome_bridge", "Website navigation": "W:pc_actions browser_*",
        "Web login assistance": "C:site credentials", "Table extraction": "N",
        "Data extraction": "P:chrome_bridge", "Article comparison": "M",
        "Search-result filtering": "M", "Research report generation": "M",
        "Website change detection": "N", "FAQ extraction": "M", "Documentation lookup": "M",
        "Web archive lookup": "S:no archive API key", "Research bookmarking": "N",
    },
    "Research Lab": {
        "Literature search": "S:no paper database access",
        "Paper discovery": "S:no paper database access",
        "Paper summarization": "S:needs a paper source first",
        "Paper comparison": "M", "Citation extraction": "S:needs a paper source",
        "Research timeline": "M", "Research question generation": "M",
        "Literature-gap detection": "M", "Source credibility analysis": "M",
        "Evidence extraction": "M", "Claim verification": "M",
        "Dataset discovery": "S:no dataset access", "Research note organization": "P:server.vault_save",
        "Bibliography generation": "M", "Citation formatting": "M",
        "Experimental planning": "M", "Hypothesis management": "M",
        "Research project tracking": "N", "Research presentation creation": "N",
        "Automated research briefs": "M",
    },
    "Programming": {
        "Code generation": "M", "Code explanation": "M", "Code debugging": "M",
        "Code refactoring": "M", "Code optimization": "M", "Code review": "M",
        "Unit-test generation": "M", "Integration-test generation": "M",
        "Test execution": "P:terminal action runs the command",
        "Bug reproduction": "M", "Error-log analysis": "M", "Stack-trace analysis": "M",
        "Dependency analysis": "M", "Package discovery": "M", "Documentation generation": "M",
        "API generation": "M", "API testing": "M", "Database querying": "C:DB credentials",
        "SQL generation": "M", "Regex generation": "M", "Shell scripting": "M",
        "Git assistance": "P:terminal action runs git", "Commit generation": "M",
        "PR description generation": "M", "Repository analysis": "M",
        "Architecture analysis": "M", "Dependency updates": "M", "Migration assistance": "M",
        "Security scanning": "M", "Performance profiling": "M",
    },
    "Software Engineering Agent": {
        "Project scaffolding": "M", "Feature implementation": "M", "Issue analysis": "M",
        "Issue fixing": "M", "Codebase mapping": "M", "Architecture planning": "M",
        "Refactoring plans": "M", "Technical-debt detection": "M",
        "Documentation auditing": "M", "API compatibility checking": "M",
        "Build troubleshooting": "P:terminal action", "CI troubleshooting": "P:terminal action",
        "Deployment troubleshooting": "P:terminal action", "Log monitoring": "P:terminal action",
        "Release-note generation": "M", "Changelog generation": "M", "Semantic versioning": "M",
        "Environment configuration": "M", "Docker assistance": "S:Docker not installed",
        "Cloud deployment assistance": "C:cloud account", "Database migration planning": "M",
        "Performance optimization": "M", "Test coverage analysis": "M",
        "Code-quality analysis": "M", "Developer onboarding": "M",
    },
    "Data Science": {
        "CSV analysis": "S:no pandas installed", "Excel analysis": "S:no openpyxl installed",
        "Data cleaning": "S:no pandas installed", "Missing-value detection": "S:no pandas installed",
        "Outlier detection": "M", "Data transformation": "S:no pandas installed",
        "Statistical analysis": "S:no scipy/statsmodels", "Correlation analysis": "S:no pandas",
        "Regression": "S:no scikit-learn", "Forecasting": "M", "Clustering": "S:no scikit-learn",
        "Classification": "S:no scikit-learn", "Dataset visualization": "S:no matplotlib",
        "Chart generation": "S:no matplotlib", "Dashboard generation": "N",
        "Data summarization": "M", "Pivot analysis": "S:no pandas", "KPI calculation": "M",
        "Trend detection": "M", "Anomaly detection": "M", "Data pipeline design": "M",
        "Dataset comparison": "M", "Automated reports": "M", "Data validation": "M",
        "Data quality scoring": "M",
    },
    "Business Intelligence": {
        "KPI tracking": "N", "Sales analysis": "S:no sales data source",
        "Revenue analysis": "S:no revenue data source", "Customer analysis": "S:no CRM",
        "Market research": "M", "Competitor research": "M", "SWOT analysis": "M",
        "Business-plan generation": "M", "Strategy analysis": "M", "Process optimization": "M",
        "Operations analysis": "M", "Product analysis": "M", "Customer segmentation": "M",
        "Churn analysis": "S:no customer data", "Pricing analysis": "M",
        "Forecasting": "M", "Scenario modeling": "M", "Executive briefing": "M",
        "Meeting intelligence": "S:no calendar or meeting audio", "Business report generation": "M",
    },
    "Writing": {
        "Blog writing": "M", "Article writing": "M", "Technical writing": "M",
        "Documentation": "M", "Email drafting": "P:email_integration",
        "Proposal writing": "M", "Report writing": "M", "Essay assistance": "M",
        "Script writing": "M", "Story writing": "M", "Copywriting": "M", "Editing": "M",
        "Proofreading": "M", "Tone transformation": "M", "Simplification": "M",
        "Expansion": "M", "Summarization": "M", "Paraphrasing": "M",
        "Headline generation": "M", "Outline generation": "M", "Brainstorming": "M",
        "Grammar correction": "M", "Style analysis": "M", "Readability analysis": "M",
        "Translation": "S:no translation service wired (Edge TTS speaks, does not translate)",
    },
    "Creative Studio": {
        "Idea generation": "M", "Character creation": "M", "Worldbuilding": "M",
        "Story planning": "M", "Plot analysis": "M", "Dialogue writing": "M",
        "Creative prompts": "M", "Brand-name generation": "M", "Logo concept generation": "M",
        "Design briefs": "M", "Moodboard concepts": "M", "Presentation concepts": "M",
        "Poster concepts": "M", "Thumbnail concepts": "M", "Social-media concepts": "M",
        "Video concepts": "M", "Advertisement concepts": "M", "Product concepts": "M",
        "UI concepts": "M", "Creative critique": "M",
    },
    "Video Production": {
        "Video idea generation": "M", "Script generation": "M", "Storyboard generation": "M",
        "Shot-list generation": "M", "Scene planning": "M", "Voiceover scripts": "M",
        "Subtitle generation": "M", "Caption generation": "M", "Video summarization": "S:no video decoding",
        "Video transcription": "S:no video decoding (audio STT only)", "Chapter generation": "M",
        "Highlight detection": "N", "Clip identification": "N", "Title generation": "M",
        "Thumbnail concepts": "M", "Metadata generation": "M", "Content repurposing": "M",
        "Long-video to short-video planning": "M", "Podcast to video conversion": "M",
        "Video quality analysis": "N",
    },
    "Music": {
        "Music discovery": "S:Spotify account not connected",
        "Playlist generation": "S:Spotify Premium not connected",
        "Mood-based playlists": "S:Spotify Premium not connected",
        "Genre discovery": "S:Spotify account not connected",
        "Artist discovery": "S:Spotify account not connected",
        "Music history": "N", "Song analysis": "S:needs audio analysis",
        "Album analysis": "P:spotify_api metadata when connected",
        "Music recommendations": "S:Spotify account not connected",
        "Listening statistics": "N", "Playlist organization": "S:needs connected account",
        "Music-library cleanup": "N", "Genre classification": "N",
        "Artist similarity": "N", "Music discovery radar": "N",
    },
    "Gaming": {
        "Game recommendations": "M", "Game discovery": "M", "Game-library organization": "N",
        "Game information lookup": "M", "Build planning": "M", "Strategy explanations": "M",
        "Quest tracking": "N", "Achievement tracking": "N", "Game-stat analysis": "S:no game telemetry",
        "Patch-note summaries": "M", "Game-update monitoring": "S:no scheduler for it",
        "Esports information": "M", "Tournament tracking": "N",
        "Game-server monitoring": "N", "Gaming-news briefing": "M",
    },
    "Education": {
        "Tutor mode": "M", "Concept explanation": "M", "Socratic questioning": "M",
        "Homework assistance": "M", "Practice-question generation": "M",
        "Quiz generation": "M", "Flashcard generation": "M",
        "Spaced-repetition planning": "M", "Study-plan generation": "M",
        "Exam revision": "M", "Mistake analysis": "N",
        "Learning-progress tracking": "N", "Vocabulary training": "M",
        "Language practice": "M", "Pronunciation practice": "S:no pronunciation scoring",
        "Math solving": "M", "Physics problem solving": "M", "Chemistry assistance": "M",
        "Biology assistance": "M", "History assistance": "M", "Geography assistance": "M",
        "Computer-science tutoring": "M",
    },
    "Languages": {
        "Translation": "S:no translation service wired", "Transcription": "W:speech_stt",
        "Language detection": "M", "Grammar correction": "M", "Vocabulary building": "M",
        "Pronunciation coaching": "S:no pronunciation scoring", "Conversation practice": "M",
        "Accent explanation": "M", "Idiom explanation": "M", "Slang explanation": "M",
        "Dictionary lookup": "M", "Etymology lookup": "M", "Multilingual search": "M",
        "Bilingual document conversion": "N", "Language-learning plans": "M",
        "Reading practice": "M", "Writing practice": "M", "Speaking practice": "P:tts_engine speaks back",
    },
    "Productivity": {
        "Task management": "N", "Task prioritization": "M", "Calendar management": "N",
        "Meeting preparation": "M", "Meeting summaries": "S:no meeting audio source",
        "Action-item extraction": "M", "Deadline tracking": "N", "Reminder management": "N",
        "Daily planning": "M", "Weekly planning": "M", "Focus sessions": "P:pc_actions.lock_screen_timer",
        "Project planning": "M", "Kanban management": "N", "Routine automation": "N",
        "Time blocking": "N", "Productivity analytics": "N", "Inbox organization": "P:email_integration",
        "Notification summaries": "N", "End-of-day review": "N", "Morning briefing": "S:no scheduler for it",
    },
    "Smart Home": {
        "Lights": "S:no smart-home devices", "Fans": "S:no smart-home devices",
        "AC": "S:no smart-home devices", "Thermostats": "S:no smart-home devices",
        "TVs": "S:no smart-home devices", "Speakers": "P:app_volume (PC audio only)",
        "Cameras": "S:no smart-home devices", "Doorbells": "S:no smart-home devices",
        "Smart plugs": "S:no smart-home devices", "Sensors": "S:no smart-home devices",
        "Curtains": "S:no smart-home devices", "Scenes": "S:no smart-home devices",
        "Home modes": "S:no smart-home devices", "Energy monitoring": "S:no smart meter",
        "Device health": "P:pc_actions.system_diagnostics (PC only)", "Automation rules": "N",
        "Presence detection": "N", "Room control": "S:no smart-home devices",
        "Home dashboard": "N", "Emergency alerts": "N",
    },
    "Communication": {
        "Email organization": "P:email_integration", "Email summarization": "P:email_integration",
        "Email search": "P:email_integration", "Draft replies": "M",
        "Inbox prioritization": "M", "Meeting invitations": "N", "Contact search": "N",
        "Notification summarization": "N", "Message drafting": "M",
        "Message categorization": "M", "Communication reminders": "N",
        "Follow-up tracking": "N", "Conversation summaries": "N", "Contact notes": "N",
        "Communication history": "N",
    },
    "Shopping & Products": {
        "Product discovery": "M", "Product comparison": "M",
        "Specification comparison": "M", "Price comparison": "M", "Price tracking": "S:no retailer accounts",
        "Review summarization": "S:no retailer access", "Review sentiment analysis": "S:no review source",
        "Product research": "M", "Alternative discovery": "M", "Compatibility checking": "M",
        "Shopping-list management": "N", "Deal monitoring": "S:no retailer accounts",
        "Wishlist management": "N", "Product availability monitoring": "S:no retailer accounts",
        "Purchase research": "M",
    },
    "Travel": {
        "Destination research": "M", "Trip planning": "M", "Itinerary generation": "M",
        "Hotel research": "M", "Transportation research": "M", "Route planning": "S:no maps API key",
        "Attraction discovery": "M", "Restaurant discovery": "M", "Packing lists": "M",
        "Travel checklists": "M", "Local-language assistance": "M",
        "Travel-budget planning": "M", "Weather-aware planning": "S:no weather API wired",
        "Trip document organization": "N", "Travel reminders": "N",
    },
    "Maps & Location": {
        "Place search": "S:no maps API key", "Nearby-place discovery": "S:no maps API key",
        "Route planning": "S:no maps API key", "Distance calculation": "S:no maps API key",
        "Travel-time estimation": "S:no maps API key", "Area exploration": "S:no maps API key",
        "Place comparison": "M", "Location-based reminders": "N", "Geofencing workflows": "N",
        "Local event discovery": "S:no events API",
    },
    "Personal Finance": {
        "Expense tracking": "N", "Budget planning": "M", "Spending categorization": "N",
        "Subscription tracking": "N", "Bill reminders": "N", "Financial summaries": "N",
        "Cash-flow analysis": "S:no account data", "Savings-goal tracking": "N",
        "Expense anomaly detection": "N", "Receipt organization": "N",
        "Invoice extraction": "N", "Tax-document organization": "N",
        "Financial-document summarization": "M",
    },
    "Knowledge Graph": {
        "Entity extraction": "M", "Relationship extraction": "M",
        "Knowledge graph construction": "N", "Personal knowledge graph": "N",
        "Topic graph generation": "N", "Concept linking": "M", "Knowledge-gap detection": "M",
        "Fact linking": "P:server.vault_save", "Timeline construction": "M",
        "Entity disambiguation": "M", "Knowledge-base search": "P:pc_actions.file_search",
        "Automatic knowledge updates": "N",
    },
    "Security & Privacy": {
        "Permission management": "N", "Secret detection": "W:repo secret scan (dev-time)",
        "Credential protection": "P:data/keys.json is git-ignored",
        "Sensitive-data detection": "M", "Privacy checks": "M",
        "Suspicious-link detection": "M", "Phishing detection": "M",
        "File-permission auditing": "N", "Application-permission auditing": "N",
        "Security-event monitoring": "N", "Login monitoring": "N",
        "Device-security status": "P:pc_actions.system_diagnostics", "Privacy-report generation": "M",
        "Data-access logging": "P:server request log", "Action confirmation system": "N",
    },
    "Automation": {
        "Scheduled workflows": "S:Hermes cron exists but its agent loop cannot run on this key",
        "Event-triggered workflows": "N", "File-triggered workflows": "N",
        "Time-triggered workflows": "N", "Email-triggered workflows": "N",
        "Web-triggered workflows": "N", "Multi-step automation": "P:server chained actions",
        "Conditional workflows": "N", "Retry handling": "N", "Failure recovery": "N",
        "Workflow templates": "N", "Workflow generation": "M", "Workflow debugging": "M",
        "Workflow monitoring": "N", "Automation history": "P:server action history",
    },
    "Autonomous Agent Skills": {
        "Goal execution": "M", "Autonomous research": "M", "Autonomous browsing": "P:chrome_bridge",
        "Autonomous coding": "M", "Autonomous testing": "P:terminal action",
        "Autonomous debugging": "M", "Autonomous file organization": "N",
        "Autonomous project setup": "M", "Autonomous monitoring": "P:server.proactive",
        "Autonomous reporting": "M", "Multi-agent delegation": "S:Hermes delegation needs the agent loop",
        "Agent collaboration": "S:Hermes delegation needs the agent loop",
        "Agent verification": "N", "Task recovery": "N", "Long-running tasks": "P:background threads",
        "Background jobs": "P:server background threads", "Progress reporting": "P:server.progress",
        "Human approval checkpoints": "N", "Failure diagnosis": "M", "Self-evaluation": "N",
    },
    "Futuristic JARVIS Skills": {
        "Predictive task suggestions": "P:server.proactive", "Proactive information retrieval": "P:server.proactive",
        "Context-aware recommendations": "M", "Situation awareness": "P:server.system_status",
        "Ambient assistant mode": "P:speech_stt wake word", "Voice activation": "W:speech_stt wake word",
        "Multi-device synchronization": "P:tunnel_remote phone link",
        "Cross-device continuity": "P:tunnel_remote", "Personal AI operating system": "P:Agency OS UI",
        "AI-generated workflows": "M", "Automatic skill discovery": "W:hermes_bridge.skills",
        "Automatic skill installation": "N", "Skill dependency resolution": "N",
        "Skill health monitoring": "P:hermes_bridge.status", "Skill performance analytics": "N",
        "Self-improving workflows": "N", "Personal command language": "W:server synonym catalog",
        "Natural-language macros": "P:server chained actions", "Persistent projects": "P:open_project",
        "Mission-control dashboard": "W:Agency OS UI",
    },
    "Multimodal Vision": {
        "Object recognition": "M", "Image understanding": "S:no vision model wired",
        "Screenshot understanding": "W:pc_actions.screenshot then read the file",
        "UI understanding": "S:no vision model wired", "Chart understanding": "S:no vision model wired",
        "Diagram understanding": "S:no vision model wired", "Document vision": "S:no OCR or vision model",
        "Handwriting recognition": "S:no OCR engine", "OCR": "S:no OCR engine installed",
        "Visual comparison": "N", "Image search": "M", "Scene analysis": "S:no vision model",
        "Visual question answering": "S:no vision model", "Image classification": "S:no vision model",
        "Visual anomaly detection": "N",
    },
    "Voice JARVIS": {
        "Wake-word detection": "W:speech_stt", "Voice commands": "W:speech_stt",
        "Continuous conversation": "P:speech_stt session mode", "Speaker identification": "N",
        "Voice activity detection": "P:speech_stt VAD", "Speech transcription": "W:speech_stt",
        "Speech synthesis": "W:tts_engine", "Voice selection": "P:app.js voice picker",
        "Speaking-speed control": "P:tts_engine rate", "Interruption handling": "P:speech_stt barge-in",
        "Voice confirmation": "N", "Voice shortcuts": "N", "Voice macros": "P:server chained actions",
        "Background listening modes": "P:speech_stt", "Context-aware responses": "M",
    },
    "JARVIS magic layer": {
        "Morning intelligence briefing": "S:no scheduler for it",
        "Automatic daily agenda": "S:no calendar connected",
        "What should I know briefing": "M", "What did I miss briefing": "S:no activity log source",
        "Personal command macros": "P:server chained actions",
        "Natural-language computer control": "W:pc_actions + server router",
        "One-command multi-action execution": "P:server chained actions",
        "Proactive reminders based on context": "P:server.proactive",
        "Automatic project monitoring": "P:pc_actions.system_diagnostics",
        "Automatic website monitoring": "S:no scheduler for it",
        "Automatic news monitoring": "P:server /api/news",
        "Automatic research agents": "M",
        "Background task agents": "P:server background threads",
        "Personal knowledge graph": "N", "Long-term project memory": "P:server.vault_save",
        "Cross-device memory": "P:tunnel_remote", "Context-aware skill selection": "P:server router",
        "Automatic workflow creation": "M", "Skill chaining": "P:server chained actions",
        "Skill marketplace/plugin system": "P:hermes_bridge.skills (read-only)",
        "Agent-to-agent delegation": "S:Hermes delegation needs the agent loop",
        "Human approval checkpoints": "N", "Undo/recovery system": "N",
        "Action history": "W:server action history", "Explain-what-I-did mode": "P:server action history",
        "Watch this for me mode": "S:no scheduler for it",
        "Handle this until it's done mode": "M",
        "Keep me updated mode": "P:server background threads",
        "Prepare everything mode": "M", "Find and fix it mode": "M",
    },
}

_STATUS_LEGEND = {
    "W": "working - real deterministic executor",
    "P": "partial - real executor, narrower than requested",
    "M": "model - genuinely handled by Groq in conversation",
    "C": "needs credential",
    "S": "needs service, hardware, or an integration that does not exist here",
    "N": "not implemented",
}


def _classify(code: str) -> tuple[str, str]:
    kind, _, detail = code.partition(":")
    return kind, detail


def all_capabilities() -> list:
    out = []
    for category, caps in _CATEGORIES.items():
        for name, code in caps.items():
            kind, detail = _classify(code)
            out.append({
                "category": category, "capability": name, "status": kind,
                "backing": detail,
                "description": EXECUTORS.get(detail, ""),
            })
    return out


def summary() -> dict:
    caps = all_capabilities()
    counts = {}
    for c in caps:
        counts[c["status"]] = counts.get(c["status"], 0) + 1
    return {
        "total": len(caps),
        "categories": len(_CATEGORIES),
        "by_status": {k: counts.get(k, 0) for k in ("W", "P", "M", "C", "S", "N")},
        "legend": _STATUS_LEGEND,
        "real_executors": len(EXECUTORS),
        "note": (
            "Capabilities marked M are real but generative: the Groq model handles "
            "them in conversation. W and P have deterministic executors. C, S and N "
            "are honest gaps -- JENNY reports them instead of pretending."
        ),
    }


def lookup(name: str) -> dict | None:
    target = (name or "").strip().lower()
    for c in all_capabilities():
        if c["capability"].lower() == target:
            return c
    return None
