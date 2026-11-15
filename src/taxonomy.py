"""The topic list ("taxonomy"): one shared definition used by the AI tagger, the labelling tool and the dashboard.

Design: aspect-based sentiment analysis. A review is split into separate POINTS. Each point gets
  - a TOPIC  (what it is about), and
  - a TYPE   (how the user feels about it: positive / negative / neutral, or a request for something new).
A review can have any number of points. Then the whole review gets an OVERALL sentiment.

History: v1 had a "praise" theme, which made sentiment redundant (praise is always positive) and
split opinions about the same topic into different buckets. v2 (this file) keeps topics neutral so
each topic can be loved or hated. Change topics here only, then re-run tagging and evals.
"""

TOPICS = {
    "core_features": ("A SPECIFIC named feature or capability: databases, templates, pages/blocks, calendar, "
                      "tasks/to-dos, search, widgets, tags/folders, integrations, web clipper, sharing/collaboration, "
                      "a feature being removed or missing. NOT general praise of the app for notes, organising or "
                      "work - that is 'overall'."),
    "performance": "Speed, lag, freezing, crashes, loading, app won't open, memory or battery use.",
    "editing": "Writing and editing: typing, cursor, keyboard, formatting, copy/paste, text selection, images and attachments in notes.",
    "usability_design": "Ease of learning, navigation, layout, look and feel, onboarding, how complicated it is.",
    "ai": "The built-in AI features: quality, usefulness, being forced on users, AI limits.",
    "pricing_plans": "Price, price increases, value for money, free plan limits (incl. device limits), features behind a paywall.",
    "ads_prompts": "Ads, forced videos, upgrade pop-ups, nagging to buy premium.",
    "billing": "Charges, free trials turning paid, cancelling, refunds, unauthorised payments.",
    "sync_login": "Login and logout, sync across devices, offline access, account access.",
    "data_safety": "Lost, deleted or corrupted data, backups, importing, exporting or migrating notes.",
    "support": "Customer support and help from the company.",
    "overall": ("A general verdict on the whole app, including how well it does its main job, without naming a "
                "specific feature: 'great app', 'best app for note making', 'keeps me organised', 'useful for "
                "work and study', 'my second brain', 'worst app ever', 'used to be good'. Do NOT add an overall "
                "point just for a closing remark ('don't recommend', 'uninstalling', 'going downhill') when the "
                "review already has specific complaints or praise; that feeling goes into overall_sentiment "
                "and churn_signal instead."),
    "other": "Off-topic, spam, or too unclear to place.",
}

POINT_TYPES = {
    "positive": "The user likes this.",
    "negative": "The user dislikes this or has a problem with it.",
    "neutral": "A plain statement or question with no clear feeling.",
    "request": "The user asks for something new or for something to come back.",
}

SEVERITY = {  # only for negative points
    "none": "Not a negative point.",
    "low": "Minor annoyance; the user still uses the app happily.",
    "medium": "Real friction that hurts daily use.",
    "high": "Blocks use entirely, loses data or money, or drives the user away.",
}

OVERALL = {
    "positive": "Praise only, or praise with a tiny complaint; usually 4-5 stars.",
    "mixed": "Clear praise AND a clear complaint; often 3 stars.",
    "negative": "Mostly complaints; usually 1-2 stars.",
    "neutral": "A question or plain statement with no feeling.",
}
