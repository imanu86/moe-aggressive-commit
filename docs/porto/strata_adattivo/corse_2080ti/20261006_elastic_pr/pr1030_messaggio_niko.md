@Niko1221 this is the automatic elastic cache I mentioned under #614, now as a focused PR on 0.1.39.

I know your direction in #533 is manual VRAM control, and `--vram-elastic` now does exactly that, so I kept this one
strictly opt-in and apart from it: separate method names, the two never open together, and without `--elastic` the
output is bit-identical to upstream (fixed-placement teacher forcing, byte for byte). What it adds is the case a
manual reserve cannot follow: a card shared with desktop programs whose VRAM use comes and goes while the server
runs - the cache keeps a fixed core from the profile and lets only its tail grow and shrink.

It has been the daily default on our modified 2080 Ti since September 30. If you would rather see a smaller piece
first (for example only the VMM arena, or only the core/tail split on top of `--vram-elastic`'s arena), I am happy
to reshape it. Logs and scripts: https://github.com/imanu86/Strata-2080Ti/tree/evidence/elastic-cache
