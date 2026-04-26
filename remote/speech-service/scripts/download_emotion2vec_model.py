from argparse import ArgumentParser
from pathlib import Path

from huggingface_hub import snapshot_download


def main() -> None:
    parser = ArgumentParser(description="Download emotion2vec+ model to a local directory.")
    parser.add_argument(
        "--repo-id",
        default="emotion2vec/emotion2vec_plus_base",
        help="Hugging Face repository id.",
    )
    parser.add_argument(
        "--local-dir",
        required=True,
        help="Target local directory for the model files.",
    )
    args = parser.parse_args()

    target_dir = Path(args.local_dir).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    snapshot_download(
        repo_id=args.repo_id,
        local_dir=str(target_dir),
        local_dir_use_symlinks=False,
        resume_download=True,
    )
    print(f"[ok] Downloaded {args.repo_id} to {target_dir}")


if __name__ == "__main__":
    main()
