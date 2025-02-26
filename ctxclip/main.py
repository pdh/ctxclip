import argparse
from ctxclip.expand import arg_parser as expand_parser
from ctxclip.expand import main as expand_main
from ctxclip.interface import arg_parser as interface_parser
from ctxclip.interface import main as interface_main


def main():
    parser = argparse.ArgumentParser(prog="ctxclip")
    subparsers = parser.add_subparsers(dest="command")
    expand = subparsers.add_parser("expand")
    expand_parser(expand)
    interface = subparsers.add_parser("api")
    interface_parser(interface)

    # import ipdb; ipdb.set_trace()
    args = parser.parse_args()
    if args.command == "expand":
        expand_main(args)
    elif args.command == "api":
        interface_main(args)


if __name__ == "__main__":
    main()
