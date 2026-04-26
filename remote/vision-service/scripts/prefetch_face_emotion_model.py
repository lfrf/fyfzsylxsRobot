from argparse import ArgumentParser


def main() -> None:
    parser = ArgumentParser(description="Prefetch hsemotion FER model weights.")
    parser.add_argument("--model-name", default="enet_b2_7", help="hsemotion model name")
    parser.add_argument("--device", default="cpu", help="Device for warmup (cpu or cuda:0)")
    args = parser.parse_args()

    from hsemotion.facial_emotions import HSEmotionRecognizer

    HSEmotionRecognizer(model_name=args.model_name, device=args.device)
    print(f"[ok] Prefetched hsemotion model: {args.model_name} on {args.device}")


if __name__ == "__main__":
    main()
