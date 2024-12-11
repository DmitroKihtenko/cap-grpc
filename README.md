# cap-grpc

gRPC API servers mocking tool. Like an gRPC clients tools are used to get
gRPC responses data from a web resources, this utility is used to get
gRPC requests data from some gRPC servers clients. Can be used to
analyze incoming gRPC requests data, and to simulate web applications
with static responses. Based on python `grpcio`, `jinja2` and `asyncio`
frameworks.

Supports:
1. Static mocking.
2. Dynamic mocking with 
   * templates;
   * proxy mode;
   * states;
   * custom mocks generating logic with shell-scripts and jinja2 templating;
3. Requests delaying.

Dynamic mocking is fully based on `jinja2` with `YAML` files format.
It's possible to use any built-in jinja2 functionality. Refer to
[jinja2 documentation](https://jinja.palletsprojects.com/en/stable/templates/)
for more details about templating language built-in functions.

### Installation
##### Usage with binary file
1. Download tool binary file from current repository's directory `dist`:
   * `cap-grpc` - executable file for Linux based systems
   * `cap-grpc.exe` - executable file for Windows based systems
2. Check tool works correct: run command from downloaded directory
   * `./cap-grpc --help` - for Linux
   * `cap-grpc.exe --help` - for Windows
3. Add downloaded binary file to any directory specified in PATH or create
separate directory for binary file and add this directory to PATH.

##### Usage with Python source code
Requirements: Installed `Python 3.12` interpreter. The interpreter must be
accessible from the console. Installed python `pip` package manager.
Installation:
1. Install `pipenv`:
```python -m pip install pipenv```
2. Install dependencies and create Python environment:
```python -m pipenv install```
3. Activate program python environment in console.
```python -m pipenv shell```
4. Run program:
```python main.py```

### Usage

`cap-grpc --help` - view help page

`cap-grpc` - start servers described in default config file `cap.yml` (this
file should be created and described manually)

`cap-grpc -c your_config_file.yml` - start servers described in
`your_config_file.yml`

### Configuration file

Configuration file is used to describe all gRPC servers
configurations. You can configure:
- gRPC server sockets, server `.proto` files, SSL/TLS certificates for
sockets
- gRPC responses mocks: output message/messages, error status code,
error message, response metadata
- gRPC proxy mode for specific endpoints
- general and API requests-responses logging config. This is
a part of parameters that manages viewing and saving all gRPC requests
data. You can configure logging format, properties to view and
saving body to files and others

Configuration file example:

```yaml
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
            name: "The Dictionary of Demons: Expanded and Revised: Names of the Damned"
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
  level: "DEBUG"
general_logging_config:
  console: true
  files:
    - "logs/api.logs"
  format: "yaml"
  format_line: |
    %(message)s (request_message)s %(response_message)s
    %(method)s %(service)s %(code)s %(error_details)s
    %(metadata)s %(alias)s %(timestamp)s
```

### Quick usage example:

API definitions in /home/my-user/book-service.proto:
```
syntax = "proto3";

package com.book;

message Book {
    message Author {
        string first_name = 1;
        string last_name = 2;
    };

    Enum BookType {
        COLLECTION = 0;
        ENCYCLOPEDIA = 1;
        NOVEL = 2;
        POEM = 3;
    }

    int64 id = 1;
    string name = 2;
    Author author = 3;
    BookType type = 4;
}

message BookList {
    repeated Book books = 1;
    uint32 total = 2;
}

message GetBookRequest {
    int64 id = 1;
}

message AddBookRequest {
    int64 id = 1;
}

service BookService {
    rpc GetBook (GetBookRequest) returns (Book) {}
    rpc AddBook (AddBookRequest) returns (Book) {}
    rpc GetBooksList (GetBookRequest) returns (BookList) {}
}
```

Mock server configuration file /home/my-user/book-service-mock.yml:
```yaml
servers:
  - alias: 'Book API'
    sockets:
      - socket: 'localhost:8100'
    reflection_enabled: true
    proto_files:
      - "book-service.proto"
    mocks:
      com.book.BookService:
        GetBook:
          messages:
            id: "{{message.id}}"
            name: "The Dictionary of Demons: Expanded and Revised: Names of the Damned"
            type: "ENCYCLOPEDIA"
            author:
              first_name: "Michael"
              last_name: "Belanger"
          trailing_meta:
            custom_metadata: metadata
          seconds_delay: 1
        AddBook:
          error:
            code: 16
            details: "Unauthorized. Credentials required"
          seconds_delay: 1
        GetBooksList:
          proxy: 
            socket: "original-book-service-host:8100"
            seconds_timeout: 10
```

Run mock server with configuration from /home/my-user/book-service-mock.yml:
```bash
cap-grpc -c /home/my-user/book-service-mock.yml
```

To stop server send SIGTERM or SIGINT POSIX signal (For
example CTRL + C in Linux terminal).

### Creating binary files
Pyinstaller is used for creating binary files. Instructions:
1. Configure your environment for local development as described in
`Usage from Python source code` (omit last step).
Requirements: Installed `Python 3.12` interpreter. The interpreter must be
accessible from the console. Installed python `pip` package manager.
Installation:
2. Install `pipenv`:
```python -m pip install pipenv```
3. Install dependencies and create Python environment:
```python -m pipenv install```
4. Install dependencies and create Python environment:
```python -m pipenv install```
5. Activate program python environment in console:
```python -m pipenv shell```
6. Run binaries installation:
```bash
pyinstaller --onefile --distpath ./dist --collect-all=grpc_tools -n cap-grpc src/main.py
```
7. Use binary file from `/dist`.

### Dynamic templating
Dynamic mocking is based on jinja2 templating language. Templating language
can be used only in mock config section from configuration file:
```yaml
servers:
  - alias: "Book API"
    sockets:
      - socket: "localhost:8100"
    proto_files:
      - "book-service.proto"
      - "{% set my_value = 1 %}" # jinja2 templates will be ignored here
    mocks:
      com.book.BookService:
        GetBook: |
          messages:
            id: "{{ message.id }} or 0"
        # jinja2 templates will be processed here to form gRPC responses
        # in this section or any internal section
```

#### Jinja2 modifications for dynamic mocks
1. `include` tag can load any template file from any directory by absolute or
relative path. Caching templates disabled.
2. New functions:
   * `relative` - returns file absolute path in relation to configuration file
   directory: Example: `{{ relative('my-file.yaml') }}` - if used configuration
   file path is /working-dir/cap-grpc.yml, will return
   /working-dir/my-file.yaml.
   * `insert` - inserts file content (like include tag but reads file and does
   not render it). Examples: `{{ insert('/dir/my-file.yaml') }}`,
   `{{ insert('my-file.yaml', 'ascii') }}`,
   `{{ insert('my-file.yaml', 'ascii', use_cache=True) }}`
   * `shell` - runs shell command and returns result which is object with
   attributes: `code`, `stdout`, `stderr`. Examples:
   `{{ shell('curl', '--head', 'https://google.com').code }}`,
   `{{ shell('grep', 'filter_text', stdin=my_stdin_var).stdout }}`,
   * `set_state` - sets server state. Argument can be any type value. Example:
   `{% set _ = set_state('state-1') %}`
   * `get_state` - gets server state. By default returns string type value
   `initial`. Example: `{{ get_state() }}`
3. Request context variables:
   * `messages` - list of request messages (list of dictionaries).
   * `message` - first request message
   * `metadata` - metadata dict object
   * `sockets` - list of servers sockets strings
   * `service` - dict type variable with server info
   * `method` - dict type variable with method info
   * `alias` - server's alias

#### Examples
Templates mocking:
```yaml
...
    mocks:
      com.book.BookService:
        GetBook:
          messages:
            id: "{{ message.id }} or 0"
        # jinja2 templates will be processed here to form gRPC responses
        # in this section or any internal section
```
Custom logic with jinja2 templating language:
```yaml
...
    mocks:
      com.book.BookService:
        GetBook:
          messages:
            id: "{{ message.id }} or 0"
        # jinja2 templates will be processed here to form gRPC responses
        # in this section or any internal section
