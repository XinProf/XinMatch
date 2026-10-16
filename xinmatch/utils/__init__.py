"""Application-level utilities shared by the XinMatch GUI/CLI layers.

Only stdlib-only helpers live here so that :mod:`xinmatch.core` stays free of
GUI dependencies:

* :mod:`xinmatch.utils.registration` — PolyXRD-family registration (copied
  verbatim from ``D:\\Project\\XRD\\PolyXRD-Reg\\registration.py``);
* :mod:`xinmatch.utils.build_variant` — which binary flavour this process is
  (registered release build vs. internal evaluation build).
"""
