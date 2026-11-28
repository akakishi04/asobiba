"""Dependency-free perspective projection of a fixed, neutral 3D mannequin."""
from __future__ import annotations

import math
from .camera_spec import OPTIONS, PREVIEW_DEFAULTS, normalize


def _dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def _clip(x0, y0, x1, y1, w, h):
    # Liang-Barsky: clip before handing large coordinates to Tk.
    dx, dy = x1-x0, y1-y0
    lo, hi = 0.0, 1.0
    for p, q in ((-dx, x0), (dx, w-x0), (-dy, y0), (dy, h-y0)):
        if abs(p) < 1e-12:
            if q < 0:
                return None
        elif p < 0:
            lo = max(lo, q/p)
        else:
            hi = min(hi, q/p)
        if lo > hi:
            return None
    return (x0+lo*dx, y0+lo*dy, x0+hi*dx, y0+hi*dy)


def segments(spec, width, height):
    """Return clipped 2D lines tagged grid/body/front from actual 3D coordinates."""
    if width < 2 or height < 2:
        return ()
    values = {**PREVIEW_DEFAULTS, **normalize(spec)}
    az = math.radians(OPTIONS["azimuth"][values["azimuth"]][3])
    el = math.radians(OPTIONS["elevation"][values["elevation"]][3])
    roll = math.radians(OPTIONS["roll"][values["roll"]][3])
    center, frame_height = OPTIONS["shot_size"][values["shot_size"]][3]
    fov = math.radians(OPTIONS["lens"][values["lens"]][3])
    focal = height/(2*math.tan(fov/2))
    # Camera looks at the selected framing center. Changing FOV changes
    # distance to retain approximately the selected subject size.
    distance = max(0.34, focal*frame_height/height, focal*0.65/width)
    outward = (-math.sin(az)*math.cos(el), -math.cos(az)*math.cos(el), math.sin(el))
    origin = (distance*outward[0], distance*outward[1], center+distance*outward[2])
    forward = tuple(-x for x in outward)
    right = (math.cos(az), -math.sin(az), 0.0)
    up = (math.sin(az)*math.sin(el), math.cos(az)*math.sin(el), math.cos(el))

    def project(point):
        relative = tuple(a-b for a,b in zip(point, origin))
        depth = _dot(relative, forward)
        if depth <= 0.045:
            return None
        x, y = focal*_dot(relative, right)/depth, -focal*_dot(relative, up)/depth
        return (width/2+x*math.cos(roll)-y*math.sin(roll),
                height/2+x*math.sin(roll)+y*math.cos(roll))

    result = []

    def line(a, b, kind):
        p, q = project(a), project(b)
        if p is None or q is None:
            return
        clipped = _clip(*p, *q, width, height)
        if clipped is not None:
            result.append((kind, *clipped))

    def loop(points, kind="body"):
        for a, b in zip(points, points[1:]+points[:1]):
            line(a, b, kind)

    def ring(z, rx, ry, y=0.0, n=12):
        return [(rx*math.cos(i*2*math.pi/n), y+ry*math.sin(i*2*math.pi/n), z)
                for i in range(n)]

    def tube(rings):
        for r in rings:
            loop(r)
        for a, b in zip(rings, rings[1:]):
            for p,q in zip(a,b):
                line(p,q,"body")

    # Floor reference grid; a fixed neutral figure, no external model/assets.
    for i in range(-5,6):
        t=i*0.32
        line((t,-1.6,0),(t,1.6,0),"grid")
        line((-1.6,t,0),(1.6,t,0),"grid")
    tube([ring(0.86,.15,.09),ring(1.00,.18,.11),
          ring(1.22,.14,.09),ring(1.43,.22,.11),ring(1.51,.15,.08)])
    tube([ring(1.51,.07,.065),ring(1.58,.067,.065),
          ring(1.62,.09,.09),ring(1.71,.12,.11),
          ring(1.80,.105,.095),ring(1.85,.045,.045)])
    # Nose and face-direction mark distinguish front/rear/profile.
    line((-.058,-.106,1.735),(.058,-.106,1.735),"front")
    line((0,-.106,1.735),(0,-.145,1.69),"front")
    line((0,-.145,1.69),(0,-.102,1.67),"front")

    def limb(points, radii):
        rings = []
        for (x,y,z), radius in zip(points,radii):
            rings.append([(x+radius*math.cos(i*math.pi/3),y+radius*math.sin(i*math.pi/3),z)
                          for i in range(6)])
        tube(rings)

    for side in (-1,1):
        limb([(side*.20,0,1.43),(side*.27,0,1.17),(side*.29,-.045,.94),
              (side*.29,-.06,.88)], [.064,.049,.036,.043])
        limb([(side*.10,0,.90),(side*.12,-.025,.49),(side*.13,0,.08)],
             [.086,.059,.038])
        loop([(side*.13-.048,.044,.04),(side*.13+.048,.044,.04),
              (side*.13+.048,-.15,.04),(side*.13-.048,-.15,.04)])
    return tuple(result)
