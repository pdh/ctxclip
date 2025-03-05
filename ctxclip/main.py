"""Main CLI"""

import argparse
from ctxclip.expand import arg_parser as expand_parser
from ctxclip.expand import main as expand_main
from ctxclip.interface import arg_parser as interface_parser
from ctxclip.interface import main as interface_main
from ctxclip.graph import arg_parser as graph_parser
from ctxclip.graph import main as graph_main
from ctxclip.snapshot.inject import arg_parser as snapshot_parser
from ctxclip.snapshot.inject import main as snapshot_main


def main():
    """entry to CLI"""
    parser = argparse.ArgumentParser(prog="ctxclip")
    subparsers = parser.add_subparsers(dest="command")
    expand = subparsers.add_parser("expand")
    expand_parser(expand)
    interface = subparsers.add_parser("api")
    interface_parser(interface)
    graph = subparsers.add_parser("graph")
    graph_parser(graph)
    snapshot = subparsers.add_parser("snapshot")
    snapshot_parser(snapshot)

    args = parser.parse_args()
    if args.command == "expand":
        expand_main(args)
    elif args.command == "api":
        interface_main(args)
    elif args.command == "graph":
        graph_main(args)
    elif args.command == "snapshot":
        snapshot_main(args)


if __name__ == "__main__":
    main()
