"""Rauchtest über stdio: startet den MCP-Server wie ein Client (Claude Desktop, Claude Code) und führt
eine Rechnung von `neu` bis `resolve`.

    python tests/mcp_stdio.py rechnung mcp
    python tests/mcp_stdio.py docker run -i --rm -v <gewerbe>:/gewerbe rechnung mcp

Der Gewerbe-Ordner braucht Stammdaten (`rechnung init`); angelegt wird eine Rechnung für `muster-gmbh`.
Exit 0, wenn alles grün ist. `tests/test_mcp.py` ruft ihn gegen den lokalen Server; `make schatten`
gegen den Container.
"""

import asyncio
import json
import os
import sys

from mcp import Client, StdioServerParameters


async def lauf(befehl: list[str]) -> None:
    # Ein stdio-Client gibt dem Server nur eine kleine Grundumgebung; RECHNUNG_* reicht er hier durch.
    env = {k: v for k, v in os.environ.items() if k.startswith("RECHNUNG_")}
    params = StdioServerParameters(command=befehl[0], args=befehl[1:], env=env)
    async with Client(params) as c:
        werkzeuge = {w.name for w in (await c.list_tools()).tools}
        assert {"neu", "schreiben", "resolve", "bauen", "pruefen"} <= werkzeuge, werkzeuge

        async def ruf(name: str, **args) -> str:
            ergebnis = await c.call_tool(name, args)
            text = "\n".join(getattr(x, "text", "") for x in ergebnis.content)
            assert not ergebnis.is_error, f"{name}: {text}"
            return text

        liste = json.loads(await ruf("preisliste"))["preisliste"]
        kuerzel = next(e for e in liste if e["art"] == "leistung")
        nummer = json.loads(await ruf("neu", kunde="muster-gmbh", leistungsdatum="2026-10-01",
                                      taetigkeit="Beratung nach Absprache", einordnung="beratung"))["nummer"]
        await ruf("schreiben", nummer=nummer,
                  positionen=[{"kuerzel": kuerzel["kuerzel"], "menge": 1, "einheit": kuerzel["einheit"]}])
        s = json.loads(await ruf("resolve", nummer=nummer))
        assert s["ergebnis"] == "inland" and s["preise"] == "fehlen", s
        assert "kunde" not in s
        print(f"mcp über stdio: {len(werkzeuge)} Werkzeuge, Rechnung {nummer} angelegt und aufgelöst (inland)")


if __name__ == "__main__":
    asyncio.run(lauf(sys.argv[1:]))
