"""Game tuning: difficulty presets, path geometry, and timing constants."""

# Slightly larger playfield; PATH / masks scale via _PATH_SCALE.
TRACK_SCALE = 1.0

# Extra window width so minimap + standings sit on grass, not on the track bitmap.
HUD_SIDEBAR_WIDTH = 240
_BASE_SCALE = 0.9
_PATH_SCALE = TRACK_SCALE / _BASE_SCALE

# See ``assets.PLAYFIELD_RECT`` / margins: offset track in the window so the top-left
# lap HUD clears the circuit. Minimum PATH x scales with _PATH_SCALE (~62 default).
_PLAYFIELD_CLEAR_HUD_X = 340
_PLAYFIELD_MIN_PATH_X = 56  # see _BASE_PATH
PLAYFIELD_MARGIN_LEFT = max(
    48,
    int(_PLAYFIELD_CLEAR_HUD_X - _PLAYFIELD_MIN_PATH_X * _PATH_SCALE) + 8,
)
PLAYFIELD_MARGIN_TOP = 56
PLAYFIELD_MARGIN_BOTTOM = 56

FPS = 60
# Menu can use a lower cap on very slow machines; 60 is fine after menu caching.
MENU_FPS = 60
KMH_FACTOR = 36
SPEEDO_MAX_KMH = 280

DIFFICULTIES = {
    "EASY": {
        "label": "EASY",
        "color": (110, 220, 140),
        "icon": "shield",
        "ai_speed_mult": 0.59,
        "ai_lookahead_bonus": -6,
        "ai_rotation_mult": 0.88,
        "ai_apex_strength": 0.30,
        "ai_corner_aggression": 0.78,
        "ai_accel_rate": 0.04,
        "obstacles": 0,
        "nitro_max": 9.0,
        "desc": "Cruise to the win",
    },
    "MEDIUM": {
        "label": "MEDIUM",
        "color": (255, 215, 100),
        "icon": "bolt",
        "ai_speed_mult": 0.645,
        "ai_lookahead_bonus": -4,
        "ai_rotation_mult": 0.94,
        "ai_apex_strength": 0.45,
        "ai_corner_aggression": 0.85,
        "ai_accel_rate": 0.05,
        "obstacles": 1,
        "nitro_max": 7.0,
        "desc": "A balanced challenge",
    },
    "HARD": {
        "label": "HARD",
        "color": (240, 90, 110),
        "icon": "skull",
        "ai_speed_mult": 0.81,
        "ai_lookahead_bonus": 14,
        "ai_rotation_mult": 1.55,
        "ai_apex_strength": 1.0,
        "ai_corner_aggression": 1.30,
        "ai_accel_rate": 0.10,
        "obstacles": 6,
        "nitro_max": 1.5,
        "desc": "Optimal apex line - relentless",
    },
}
DIFFICULTY_ORDER = ["EASY", "MEDIUM", "HARD"]

_BASE_PATH = [(175, 119), (110, 70), (56, 133), (70, 481), (318, 731),
              (404, 680), (418, 521), (507, 475), (600, 551), (613, 715),
              (736, 713), (734, 399), (611, 357), (409, 343), (433, 257),
              (697, 258), (738, 123), (581, 71), (303, 78), (275, 377),
              (176, 388), (178, 260)]
PATH = [(int(x * _PATH_SCALE), int(y * _PATH_SCALE)) for x, y in _BASE_PATH]

_BASE_NITRO_PADS = [(70, 300), (320, 700), (650, 600), (700, 200)]
NITRO_PAD_POSITIONS = [(int(x * _PATH_SCALE), int(y * _PATH_SCALE))
                       for x, y in _BASE_NITRO_PADS]

COUNTDOWN_SECONDS = 4.5
LIGHT_INTERVAL = 0.7
LIGHTS_OUT_AT = LIGHT_INTERVAL * 5
RACE_BEGINS_AT = LIGHTS_OUT_AT
