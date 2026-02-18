from __future__ import annotations

import argparse
import sys
from pathlib import Path

from modekeeper.adapters.lightning import LIGHTNING_AVAILABLE, build_lightning_callback

try:
    import torch
except Exception:
    torch = None

try:
    import pytorch_lightning as pl
except Exception:
    try:
        import lightning.pytorch as pl
    except Exception:
        pl = None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="report/_pl", help="Output directory")
    args = parser.parse_args()

    if torch is None or pl is None or not LIGHTNING_AVAILABLE:
        print("PyTorch/Lightning not installed; skipping demo.")
        return 0

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    callback = build_lightning_callback(out_dir)
    if callback is None:
        print("PyTorch/Lightning not installed; skipping demo.")
        return 0

    class TinyModule(pl.LightningModule):
        def __init__(self) -> None:
            super().__init__()
            self.linear = torch.nn.Linear(4, 1)

        def training_step(self, batch, batch_idx):
            x, y = batch
            y_hat = self.linear(x)
            loss = torch.nn.functional.mse_loss(y_hat, y)
            return loss

        def configure_optimizers(self):
            return torch.optim.SGD(self.parameters(), lr=0.01)

    x = torch.randn(8, 4)
    y = torch.randn(8, 1)
    dataset = torch.utils.data.TensorDataset(x, y)
    loader = torch.utils.data.DataLoader(dataset, batch_size=2, shuffle=False)

    trainer = pl.Trainer(
        max_steps=2,
        logger=False,
        enable_checkpointing=False,
    )
    trainer.fit(TinyModule(), train_dataloaders=loader, callbacks=[callback])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
