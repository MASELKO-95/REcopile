"""Declared project capabilities; an unknown capability is never inferred."""
from .network import UserError

TECHNOLOGIES = {
    'vulkan':'Vulkan', 'opengl':'OpenGL', 'directx9':'DirectX 9', 'directx11':'DirectX 11',
    'directx12':'DirectX 12', 'dxvk':'DXVK', 'vkd3d':'VKD3D-Proton',
    'dlss':'DLSS', 'fsr':'FSR', 'xess':'XeSS', 'ray-tracing':'Ray tracing',
    'hdr':'HDR', 'ultrawide':'Ultrawide', 'controller':'Controller',
    'keyboard-mouse':'Keyboard / mouse', 'multiplayer':'Multiplayer',
    'godot':'Godot', 'sdl':'SDL', 'static-recompilation':'Static recompilation',
}
TAGS = {'action':'Akcja', 'adventure':'Przygodowa', 'racing':'Wyścigi', 'platformer':'Platformowa',
        'rpg':'RPG', 'puzzle':'Łamigłówki', 'sports':'Sport', 'simulation':'Symulacja',
        'strategy':'Strategia', 'horror':'Horror', 'casual':'Relaks', 'singleplayer':'Jeden gracz',
        'multiplayer':'Wielu graczy', 'experimental':'Eksperymentalna', 'source-only':'Tylko źródła'}

def validate_labels(value, field):
    items = value.get(field, [])
    if (not isinstance(items, list) or len(items)>40
            or any(not isinstance(t,str) or not 1<=len(t)<=60 or t!=t.strip() or not t.isprintable() for t in items)
            or len({t.casefold() for t in items})!=len(items)):
        raise UserError('Niepoprawna lista technologii lub tagów.')

def declared(game, sources):
    keys = list(dict.fromkeys([*game.get('technologies', []), *(t for s in sources for t in s.get('technologies', []))]))
    return [{'id':key, 'label':TECHNOLOGIES.get(key,key)} for key in keys]
