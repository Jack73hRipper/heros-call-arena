# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Arena Server
Bundles the FastAPI backend into a standalone arena-server.exe

Usage (from repo root):
    cd server
    pyinstaller ../scripts/arena-server.spec
"""

import os
from pathlib import Path

block_cipher = None

# Paths relative to the spec file location
repo_root = os.path.abspath(os.path.join(SPECPATH, '..'))
server_dir = os.path.join(repo_root, 'server')

a = Analysis(
    [os.path.join(server_dir, 'app', 'main.py')],
    pathex=[server_dir],
    binaries=[],
    datas=[
        # Bundle config files (JSON configs, maps, themes, WFC modules/rulesets)
        (os.path.join(server_dir, 'configs'), 'configs'),
        # Bundle data directory (match_history, players — starts empty but needed)
        (os.path.join(server_dir, 'data'), 'data'),
    ],
    hiddenimports=[
        # Uvicorn internals (not discovered by static analysis)
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.loops.asyncio',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.http.httptools_impl',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.protocols.websockets.websockets_impl',
        'uvicorn.protocols.websockets.wsproto_impl',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'uvicorn.lifespan.off',
        # FastAPI / Starlette internals
        'fastapi',
        'fastapi.middleware',
        'fastapi.middleware.cors',
        'starlette.responses',
        'starlette.websockets',
        # Pydantic
        'pydantic',
        'pydantic_settings',
        # Redis
        'redis',
        'redis.asyncio',
        'hiredis',
        # Scheduler
        'apscheduler',
        'apscheduler.schedulers.background',
        'apscheduler.triggers.interval',
        # WebSockets
        'websockets',
        'websockets.legacy',
        'websockets.legacy.server',
        # HTTP tools
        'httptools',
        # App modules (ensure all sub-packages are found)
        'app.config',
        'app.models',
        'app.models.actions',
        'app.models.items',
        'app.models.match',
        'app.models.player',
        'app.models.profile',
        'app.core',
        'app.core.combat',
        'app.core.turn_resolver',
        'app.core.match_manager',
        'app.core.map_loader',
        'app.core.fov',
        'app.core.skills',
        'app.core.loot',
        'app.core.spawn',
        'app.core.ai_behavior',
        'app.core.ai_pathfinding',
        'app.core.ai_skills',
        'app.core.ai_stances',
        'app.core.ai_memory',
        'app.core.ai_patrol',
        'app.core.wave_spawner',
        'app.core.equipment_manager',
        'app.core.item_generator',
        'app.core.set_bonuses',
        'app.core.auto_target',
        'app.core.party_manager',
        'app.core.hero_manager',
        'app.core.monster_rarity',
        # Skill effects sub-package
        'app.core.skill_effects',
        'app.core.skill_effects._helpers',
        'app.core.skill_effects.buff',
        'app.core.skill_effects.damage',
        'app.core.skill_effects.debuff',
        'app.core.skill_effects.heal',
        'app.core.skill_effects.movement',
        'app.core.skill_effects.summon',
        'app.core.skill_effects.utility',
        # Turn phases sub-package
        'app.core.turn_phases',
        'app.core.turn_phases.helpers',
        'app.core.turn_phases.items_phase',
        'app.core.turn_phases.portal_phase',
        'app.core.turn_phases.buffs_phase',
        'app.core.turn_phases.auras_phase',
        'app.core.turn_phases.movement_phase',
        'app.core.turn_phases.interaction_phase',
        'app.core.turn_phases.skills_phase',
        'app.core.turn_phases.combat_phase',
        'app.core.turn_phases.deaths_phase',
        # WFC sub-package
        'app.core.wfc',
        'app.core.wfc.wfc_engine',
        'app.core.wfc.dungeon_generator',
        'app.core.wfc.dungeon_styles',
        'app.core.wfc.room_decorator',
        'app.core.wfc.connectivity',
        'app.core.wfc.map_exporter',
        'app.core.wfc.module_utils',
        'app.core.wfc.presets',
        # Services
        'app.services.websocket',
        'app.services.tick_loop',
        'app.services.message_handlers',
        'app.services.persistence',
        'app.services.redis_client',
        'app.services.scheduler',
        # Routes
        'app.routes.lobby',
        'app.routes.match',
        'app.routes.town',
        'app.routes.maps',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Trim unnecessary packages to reduce bundle size
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'PIL',
        'pandas',
        'IPython',
        'jupyter',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='arena-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Console app (server logs to stdout)
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='arena-server',
)
