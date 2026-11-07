"""MMPX 2x pixel-art magnification.

Port of McGuire & Gagiu, "MMPX Style-Preserving Pixel-Art Magnification",
Journal of Graphics Techniques 2021. Each output pixel is copied from an input
pixel and never blended, so the output uses exactly the input's palette.

Neighbourhood around E (the pixel being magnified):

            P
        A   B   C
    Q   D   E   F   R
        G   H   I
            S

E becomes the 2x2 block   J K
                          L M
"""

from __future__ import annotations

from .grid import Grid, luma


def _all_eq2(b, a0, a1):
    return b == a0 and b == a1


def _all_eq3(b, a0, a1, a2):
    return b == a0 and b == a1 and b == a2


def _all_eq4(b, a0, a1, a2, a3):
    return b == a0 and b == a1 and b == a2 and b == a3


def _any_eq3(b, a0, a1, a2):
    return b == a0 or b == a1 or b == a2


def _none_eq2(b, a0, a1):
    return b != a0 and b != a1


def _none_eq4(b, a0, a1, a2, a3):
    return b != a0 and b != a1 and b != a2 and b != a3


def mmpx2x(src: Grid) -> Grid:
    w, h = src.width, src.height
    out = [0] * (w * 2 * h * 2)
    ow = w * 2
    s = src.get

    for y in range(h):
        for x in range(w):
            A, B, C = s(x - 1, y - 1), s(x, y - 1), s(x + 1, y - 1)
            D, E, F = s(x - 1, y), s(x, y), s(x + 1, y)
            G, H, I = s(x - 1, y + 1), s(x, y + 1), s(x + 1, y + 1)
            J = K = L = M = E

            if A != E or B != E or C != E or D != E or F != E or G != E or H != E or I != E:
                P, Q, R, S = s(x, y - 2), s(x - 2, y), s(x + 2, y), s(x, y + 2)
                Bl, Dl, El, Fl, Hl = luma(B), luma(D), luma(E), luma(F), luma(H)

                # 1:1 slope rules
                if (D == B and D != H and D != F) and (El >= Dl or E == A) and _any_eq3(E, A, C, G) and (El < Dl or A != D or E != P or E != Q):
                    J = D
                if (B == F and B != D and B != H) and (El >= Bl or E == C) and _any_eq3(E, A, C, I) and (El < Bl or C != B or E != P or E != R):
                    K = B
                if (H == D and H != F and H != B) and (El >= Hl or E == G) and _any_eq3(E, A, G, I) and (El < Hl or G != H or E != S or E != Q):
                    L = H
                if (F == H and F != B and F != D) and (El >= Fl or E == I) and _any_eq3(E, C, G, I) and (El < Fl or I != H or E != R or E != S):
                    M = F

                # Intersection rules
                if (E != F and _all_eq4(E, C, I, D, Q) and _all_eq2(F, B, H)) and F != s(x + 3, y):
                    K = M = F
                if (E != D and _all_eq4(E, A, G, F, R) and _all_eq2(D, B, H)) and D != s(x - 3, y):
                    J = L = D
                if (E != H and _all_eq4(E, G, I, B, P) and _all_eq2(H, D, F)) and H != s(x, y + 3):
                    L = M = H
                if (E != B and _all_eq4(E, A, C, H, S) and _all_eq2(B, D, F)) and B != s(x, y - 3):
                    J = K = B

                # Triangle tips
                if Bl < El and _all_eq4(E, G, H, I, S) and _none_eq4(E, A, D, C, F):
                    J = K = B
                if Hl < El and _all_eq4(E, A, B, C, P) and _none_eq4(E, D, G, I, F):
                    L = M = H
                if Fl < El and _all_eq4(E, A, D, G, Q) and _none_eq4(E, B, C, I, H):
                    K = M = F
                if Dl < El and _all_eq4(E, C, F, I, R) and _none_eq4(E, B, A, G, H):
                    J = L = D

                # 2:1 slope rules
                if H != B:
                    if H != A and H != E and H != C:
                        if _all_eq3(H, G, F, R) and _none_eq2(H, D, s(x + 2, y - 1)):
                            L = M
                        if _all_eq3(H, I, D, Q) and _none_eq2(H, F, s(x - 2, y - 1)):
                            M = L
                    if B != I and B != G and B != E:
                        if _all_eq3(B, A, F, R) and _none_eq2(B, D, s(x + 2, y + 1)):
                            J = K
                        if _all_eq3(B, C, D, Q) and _none_eq2(B, F, s(x - 2, y + 1)):
                            K = J
                if F != D:
                    if D != I and D != E and D != C:
                        if _all_eq3(D, A, H, S) and _none_eq2(D, B, s(x + 1, y + 2)):
                            J = L
                        if _all_eq3(D, G, B, P) and _none_eq2(D, H, s(x + 1, y - 2)):
                            L = J
                    if F != E and F != A and F != G:
                        if _all_eq3(F, C, H, S) and _none_eq2(F, B, s(x - 1, y + 2)):
                            K = M
                        if _all_eq3(F, I, B, P) and _none_eq2(F, H, s(x - 1, y - 2)):
                            M = K

            i = (2 * y) * ow + 2 * x
            out[i], out[i + 1] = J, K
            out[i + ow], out[i + ow + 1] = L, M

    return Grid(ow, h * 2, out)
