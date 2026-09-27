# Publication validation

The standalone package was tested in a fresh Python 3.12 virtual environment on
Linux/WSL2. PyTorch was not installed in that environment.

- Editable installation compiled the bundled C++ snapshot library successfully.
- A distributable wheel built successfully and contained the native extension.
- **5 tests passed**: emulator parity and nested snapshot restoration; owner and
  lifetime checks; finite-horizon termination; search backtracking and deadline
  prefixes in a deterministic test world; reference replay of a successful and
  a partial archived route.
- **All 32 published action traces replayed successfully through verification**:
  29 reached the native goal and 3 reproduced their documented partial routes.
  This validation replayed existing data; it did not repeat the long searches.
- The extracted wrappers matched the previous experiment's pixels, rewards,
  terminal flags and game information exactly for 96 decisions each in 1-1,
  2-2, 4-4 and 7-4.
- MP4 encoding was exercised through the public replay CLI.
- The three README GIFs were generated from the recorded videos; file hashes
  and conversion settings are recorded in `assets/demos.json`.

The historical search results and their limits are described in the README.
This validation establishes packaging and replay consistency, not a new claim
that this package independently re-ran the complete 32-level search benchmark.
