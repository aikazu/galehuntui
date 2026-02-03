from textual.theme import Theme

# 1. Phantom (Default)
PHANTOM = Theme(
    name="phantom",
    primary="#00f2ea",
    secondary="#ff0055",
    accent="#7000ff",
    foreground="#e2e8f0",
    background="#0f111a",
    surface="#1a1c29",
    panel="#26293b",
    success="#00ff9d",
    warning="#ffb700",
    error="#ff3333",
    variables={
        "border": "#2e344d",
        "border-blurred": "#2e344d",
    },
    luminosity_spread=0.15,
)

# 2. Red Team (Crimson)
REDTEAM = Theme(
    name="redteam",
    primary="#dc143c",  # Crimson
    secondary="#8a001a",
    accent="#ff4d4d",
    foreground="#f0f0f0",
    background="#1a0505",
    surface="#2d0a0a",
    panel="#400f0f",
    success="#00ff9d",
    warning="#ffb700",
    error="#ff3333",
    variables={
        "border": "#591414",
        "border-blurred": "#591414",
    },
    luminosity_spread=0.15,
)

# 3. Matrix (Terminal Green)
MATRIX = Theme(
    name="matrix",
    primary="#00ff00",
    secondary="#008f11",
    accent="#003b00",
    foreground="#d0ffd0",
    background="#000000",
    surface="#051a05",
    panel="#0a290a",
    success="#00ff9d",
    warning="#ffb700",
    error="#ff3333",
    variables={
        "border": "#004400",
        "border-blurred": "#004400",
    },
    luminosity_spread=0.15,
)

# 4. Synthwave (Hot Pink)
SYNTHWAVE = Theme(
    name="synthwave",
    primary="#ff00ff",
    secondary="#00ffff",
    accent="#ff0099",
    foreground="#ffffff",
    background="#2b213a",
    surface="#372a4d",
    panel="#453663",
    success="#00ff9d",
    warning="#ffb700",
    error="#ff3333",
    variables={
        "border": "#5e4b85",
        "border-blurred": "#5e4b85",
    },
    luminosity_spread=0.15,
)

# 5. Midnight (Blue)
MIDNIGHT = Theme(
    name="midnight",
    primary="#3a86ff",
    secondary="#4cc9f0",
    accent="#4361ee",
    foreground="#e0e7ff",
    background="#0a0e17",
    surface="#111827",
    panel="#1f2937",
    success="#00ff9d",
    warning="#ffb700",
    error="#ff3333",
    variables={
        "border": "#374151",
        "border-blurred": "#374151",
    },
    luminosity_spread=0.15,
)

# 6. Obsidian (Zinc/Gray)
OBSIDIAN = Theme(
    name="obsidian",
    primary="#a1a1aa",
    secondary="#ffffff",
    accent="#71717a",
    foreground="#f4f4f5",
    background="#09090b",
    surface="#18181b",
    panel="#27272a",
    success="#00ff9d",
    warning="#ffb700",
    error="#ff3333",
    variables={
        "border": "#3f3f46",
        "border-blurred": "#3f3f46",
    },
    luminosity_spread=0.15,
)

# 7. Aurora (Teal/Northern Lights)
AURORA = Theme(
    name="aurora",
    primary="#2dd4bf",
    secondary="#818cf8",
    accent="#c084fc",
    foreground="#f0fdfa",
    background="#022c22",
    surface="#064e3b",
    panel="#065f46",
    success="#00ff9d",
    warning="#ffb700",
    error="#ff3333",
    variables={
        "border": "#059669",
        "border-blurred": "#059669",
    },
    luminosity_spread=0.15,
)

# 8. Sunset (Orange)
SUNSET = Theme(
    name="sunset",
    primary="#f97316",
    secondary="#ec4899",
    accent="#eab308",
    foreground="#fff7ed",
    background="#431407",
    surface="#7c2d12",
    panel="#9a3412",
    success="#00ff9d",
    warning="#ffb700",
    error="#ff3333",
    variables={
        "border": "#ea580c",
        "border-blurred": "#ea580c",
    },
    luminosity_spread=0.15,
)

# 9. Ocean (Sky Blue)
OCEAN = Theme(
    name="ocean",
    primary="#0ea5e9",
    secondary="#0284c7",
    accent="#38bdf8",
    foreground="#f0f9ff",
    background="#082f49",
    surface="#0c4a6e",
    panel="#075985",
    success="#00ff9d",
    warning="#ffb700",
    error="#ff3333",
    variables={
        "border": "#0369a1",
        "border-blurred": "#0369a1",
    },
    luminosity_spread=0.15,
)

# 10. Manuscript (Light Mode)
MANUSCRIPT = Theme(
    name="manuscript",
    primary="#2563eb",
    secondary="#4b5563",
    accent="#d97706",
    foreground="#1f2937",
    background="#ffffff",
    surface="#f3f4f6",
    panel="#e5e7eb",
    success="#16a34a",
    warning="#ca8a04",
    error="#dc2626",
    variables={
        "border": "#d1d5db",
        "border-blurred": "#d1d5db",
    },
    luminosity_spread=0.15,
)

GALEHUNT_THEMES = {
    "phantom": PHANTOM,
    "redteam": REDTEAM,
    "matrix": MATRIX,
    "synthwave": SYNTHWAVE,
    "midnight": MIDNIGHT,
    "obsidian": OBSIDIAN,
    "aurora": AURORA,
    "sunset": SUNSET,
    "ocean": OCEAN,
    "manuscript": MANUSCRIPT,
}
