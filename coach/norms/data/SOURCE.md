# CaddieSet — vendored dataset

`CaddieSet.csv` in this directory is the official dataset from:

> **CaddieSet: A Golf Swing Dataset with Human Joint Features and Ball Information**
> Jung, Hong, Jeong, Jeong, Choi, Kim, Lee. CVPR 2025 Workshop (CVSPORTS).

- Source: https://github.com/damilab/CaddieSet
- Copyright (c) 2024 damilab. Licensed under the **MIT License** (redistribution
  permitted with attribution — see the MIT terms reproduced below).
- The CSV is vendored **unmodified** from the upstream `data/CaddieSet.csv`.

## Why it is here

`coach/norms/build_norms.py` reads this CSV to compute population "typical range"
bands (p10–median–p90) for the small subset of our metrics whose geometric
definition genuinely matches a CaddieSet feature. These are **mixed-skill
population ranges, NOT validated ideal/good-bad thresholds.** Most of our metrics
cannot be sourced from CaddieSet (unit/axis mismatch) and are left
`confidence:"none"` so the coach falls back to the player's own history.

## Citation

    @inproceedings{jung2025caddieset,
      title={CaddieSet: A Golf Swing Dataset with Human Joint Features and Ball Information},
      author={Jung, Seunghyeon and Hong, Seoyoung and Jeong, Jiwoo and Jeong, Seungwon and Choi, Jaerim and Kim, Hoki and Lee, Woojin},
      booktitle={Proceedings of the Computer Vision and Pattern Recognition Conference},
      pages={5988--5996},
      year={2025}
    }

## MIT License (CaddieSet)

MIT License

Copyright (c) 2024 damilab

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
