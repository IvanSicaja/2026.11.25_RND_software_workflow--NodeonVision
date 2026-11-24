2026.11.24_GitHub_PRJ_Nodeon_SmartCodeACADEMY_Official/
│
│
├── .gitignore                                      # Files Git ignores (Python cache, PyInstaller build output, .NET test build output)
│
├── README.md                                       # Project overview: how to start Nodeon, shortcuts, Item details panel, tests
│
├── directory-structure-explained.md                # This file - what belongs in which folder
│
├── draft_requirements_python-3.11.9.txt            # Python packages to run Nodeon (PySide6): pip install -r <this file>
│
├── git_light.txt                                   # Short Git cheat sheet for this project
│
├── assets/                                         # Additional project resources (non-code)
│   │
│   ├── 01_media/                                   # Organized media resources
│   │   │
│   │   ├── 01_icons                                # Icons used in UI, documentation, branding
│   │   ├── 02_figures                              # Diagrams, charts, screenshots, illustrations
│   │   ├── 03_sounds                               # Audio assets (alerts, UI sounds, background)
│   │   ├── 04_videos                               # Demo videos, screen recordings, previews
│   │   └── 05_ads                                  # Marketing visuals: README thumbnails, banners, ad creatives, social media posts
│   └── 02_3d-modeling                              # 3D objects (STL, GLB, OBJ), CAD files, simulation models, renders
│
├── bills                                           # Financial records: invoices, receipts, subscriptions, tool / hardware / service costs
│
├── copyright                                       # Licenses, third-party attributions (e.g. PySide6 / Qt), authorship and usage rights
│
├── data                                            # Example trees to open in Nodeon (example_project_tree.txt)
│
├── docs/                                           # Documentation & written materials
│   │
│   └── 01_skills-used/                             # Skills and technologies used in this project
│       │
│       └── skills.txt                              # List of languages, frameworks, test tools and methods used
│
├── main                                            # Production source code: main.py (start this), treemodel.py, itemdetails.py - keep all three together
│
├── models/                                         # Machine learning / AI models (<100 MB locally; not used by Nodeon)
│   │
│   ├── 01_downloaded                               # Pre-trained or externally sourced models
│   └── 02_trained                                  # Models trained within this project
│
├── notebooks                                       # Jupyter / Colab notebooks: experiments, prototypes (archived snapshots)
│
├── publish                                         # Final deliverables: main.exe (PyInstaller build), installers, packaged releases
│
├── tests                                           # Developer tests (test_*.py) + test_automation/ (full verification package, CI in test_automation/ci/)
│
└── viz/                                            # Visualization outputs & dashboards
    │
    ├── 01_mind-maps                                # Mind maps, conceptual maps, system diagrams (XMind, Miro exports)
    └── 02_tableau                                  # Tableau workbooks (.twb, .twbx)
