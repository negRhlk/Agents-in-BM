# Third-party notices

This repository contains only original code, plus a patch for BMSim. Third-party
software is **not** redistributed here. It is installed from PyPI (`requirements.txt`)
or downloaded from upstream by `setup_bmsim.sh`. Each project stays under its own
license, as listed below.

## BMSim, downloaded by `setup_bmsim.sh` and modified by `patches/bmsim_hooks.patch`

* Upstream: https://github.com/BMSimulator/BMSim (tested at commit `7c6af2a`)
* Copyright: Zohreh Hosseinkhani and Majid Nabi
* License: the upstream repository has no license file. The authors provide BMSim
  publicly for research and ask for citation. `patches/bmsim_hooks.patch` modifies
  their code and is published with the authors' knowledge. It is **not** covered by
  this repository's GPL license; rights to BMSim remain with its authors.
* Citation: Z. Hosseinkhani and M. Nabi, "BMSim: An Event-Driven Simulator for
  Performance Evaluation of Bluetooth Mesh Networks", IEEE Internet of Things
  Journal, 2023. https://ieeexplore.ieee.org/document/10171234
* BMSim bundles `pymobility`. Copyright (C) 2008-2010 Istituto per l'Interscambio
  Scientifico I.S.I. Written by André Panisson. The patch does not modify it.

## Python dependencies, installed from PyPI

| Package | License | Upstream |
|---|---|---|
| spade | MIT | https://github.com/javipalanca/spade |
| spade_bdi | MIT | https://github.com/javipalanca/spade_bdi |
| agentspeak (python-agentspeak) | GPL-3.0 | https://github.com/niklasf/python-agentspeak |
| pyjabber | MIT | https://github.com/DinoThor/PyJabber |
| slixmpp-multiplatform | MIT | https://pypi.org/project/slixmpp-multiplatform/ |
| loguru | MIT | https://github.com/Delgan/loguru |
| SQLAlchemy | MIT | https://www.sqlalchemy.org |
| greenlet | MIT AND PSF-2.0 | https://github.com/python-greenlet/greenlet |
| networkx | BSD-3-Clause | https://networkx.org |
| numpy | BSD-3-Clause (and others) | https://numpy.org |
| matplotlib | PSF-based (Matplotlib License) | https://matplotlib.org |

Because python-agentspeak is GPL-3.0, this repository's own code is released under
GPL-3.0-or-later.
