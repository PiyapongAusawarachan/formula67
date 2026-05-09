# Credits — Formula 67

What is **not** original art/code is listed here so markers can check licenses.

## Car sprites (player + AI)

Files in `imgs/`: **red-car.png**, **green-car.png**, **purple-car.png**, **white-car.png**, **grey-car.png**.

I generated these with an **AI image tool** from my own prompts, then exported as PNG and used them as-is or with small edits in an image editor. They are **not** copied from a single downloadable “car pack” site.

## Other bitmaps in `imgs/`

These were found online as **reference / inspiration**; I may have cropped or recoloured them for the game.

| File | Role | Reference |
|------|------|-----------|
| grass.png | Background | <https://www.shutterstock.com/th/search/grass-game-texture?dd_referrer=https%3A%2F%2Fwww.google.com%2F> |
| track.png | Road surface | <https://www.pngwing.com/en/search?q=race+track> |
| track-border.png | Walls + collision mask source | <https://www.pngwing.com/en/search?q=race+track> |
| finish.png | Chequered strip | <https://www.freepik.com/premium-vector/background-black-white-squares-chess-board-vector_26468292.htm> |

If I later used AI or hand-drew changes on top of these, the spirit is still: **third-party look-alikes credited here**, **cars are explicitly AI-assisted**.

## Generated in this project (no external image file)

- Everything under **`reports/`** comes from **matplotlib** + `visualize.py` + `stats/*.csv`.  
- **Menu, HUD, results UI** (panels, podium, charts-on-screen) are drawn with **pygame** in code, not pasted PNGs.

## Libraries

See **requirements.txt** — mainly **pygame**, **matplotlib**, **numpy**, **pandas**.

---

*One-line summary for reports:* car sprites — AI from my prompts; track/grass/finish — links above; telemetry charts — my code.
