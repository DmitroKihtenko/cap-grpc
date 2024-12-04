from argparse import Namespace, ArgumentParser


def get_args() -> Namespace:
    arg_parser = ArgumentParser(
        prog="cap-grpc",
        description="gRPC API mocking tool")
    arg_parser.add_argument(
        "-c",
        default="cap-grpc.yml",
        metavar="config file",
        type=str,
        help="configuration .yml file path")
    arg_parser.add_argument(
        "-e",
        default=None,
        action='store_true',
        help="print configuration file examples and exit"
    )
    parsed = arg_parser.parse_args()

    if parsed.e:
        print(
"""
YAML config file example:

servers:
  - alias: 'Book API'
    sockets:
      - socket: 'localhost:8100'
      - socket: 'my.domain:8201'
        certificates:
          certificate: "certificate.pem"
          key_file: "certificate.key"
          root_certificate: "/certs/root-cert.crt"
    reflection_enabled: true
    proto_files:
      - "types/*.proto"
      - "*.proto"
    proto_files_base_dir: "./"
    mocks:
      com.book.BookService:
        GetBook:
          messages:
            id: "{{message.id}}"
            name: "Expanded and Revised: Names of the Damned"
            type: "ENCYCLOPEDIA"
            author:
              first_name: "Michael"
              last_name: "Belanger"
          trailing_meta:
            custom_metadata: metadata
        AddBook:
          error:
            code: 16
            details: "Unauthorized. Credentials required"
        GetBooksList:
          proxy: 
            socket: "original-book-service-host:8100"
            seconds_timeout: 10
api_logging_config:
  console: false
  files:
    - "logs/program.logs"
  format: "text"
  format_line: "%(levelname)s: %(message)s"
  level: "INFO"
general_logging_config:
  console: true
  files:
    - "logs/api.logs"
  format: "yaml"
  format_line: |
    %(message)s (request_message)s %(response_message)s
    %(method)s %(service)s %(code)s %(error_details)s
    %(metadata)s %(alias)s %(timestamp)s
  level: "DEBUG"
"""
        )
        exit(0)
    return parsed


args: Namespace = get_args()
