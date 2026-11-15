"""The theme list ("taxonomy"): one shared definition used by the AI tagger, the labelling tool and the dashboard.

Drafted by reading a stratified sample of 145 reviews (both apps, all star ratings) and grouping
similar complaints (affinity mapping). Change themes here only, then re-run tagging and evals.
"""

THEMES = {
    "performance": "Lag, slowness, freezing, crashes, app won't open or load, heavy on memory or battery.",
    "editor_content": "Writing and editing problems: typing or cursor bugs, keyboard issues, copy/paste, text selection, formatting, images and attachments in notes.",
    "pricing_free_plan": "Price too high or rising, free plan too limited (including device limits), features locked behind a paid plan.",
    "ads_upsell": "Ads, forced videos, upgrade pop-ups and nagging to buy premium.",
    "billing_trust": "Charged without consent, free trial silently turning paid, can't cancel, refund problems.",
    "ai_features": "Anything about the built-in AI: quality, AI being forced on users, AI limits or AI paywall, or praise for AI.",
    "account_sync": "Login or logout problems, login loops, sync failures, multi-device or offline sync issues.",
    "data_loss_export": "Lost, deleted or corrupted notes or files, can't access old notes, trouble importing or exporting/migrating.",
    "ease_of_use": "Hard to learn, confusing navigation, too complicated, poor UI or design, bad onboarding.",
    "feature_request": "Asks for a specific missing feature (e.g. widgets, OCR, fonts, bulk upload).",
    "support": "Customer support is slow, unreachable or unhelpful.",
    "praise": "General positive feedback: useful for organising, studying, productivity, love the app.",
    "other": "None of the above, or too vague to place.",
}

SENTIMENTS = ["positive", "mixed", "negative"]

SEVERITY = {
    "low": "Minor annoyance; the user still uses the app happily.",
    "medium": "Real friction that hurts daily use.",
    "high": "Blocks use entirely, loses data or money, or the user says they are leaving.",
}
