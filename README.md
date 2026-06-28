# Atletika Live — Skok o tyč Dashboard

Live dashboard pro sledování výsledků MČR z webu [online.atletika.cz](https://online.atletika.cz).

## Co to dělá

- Stahuje výsledky ze `online.atletika.cz` každých 60 sekund
- Zobrazuje přehlednou tabulku s pokusy (O / X / -)
- Funguje jako startlist (PB/SB) i live výsledková tabule
- Přístupné z libovolného zařízení na stejné WiFi

## Spuštění

```bash
python server.py
```

Otevři `http://localhost:8765` v prohlížeči.

Z telefonu (stejná WiFi): `http://<IP-počítače>:8765`

## Závislosti

Žádné — pouze Python 3 (standardní knihovny).
