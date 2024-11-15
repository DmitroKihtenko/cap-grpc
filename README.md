# cap-grpc

gRPC API servers mocking tool. Just as gRPC clients tools are used to get
gRPC responses data from a web resources, this utility is used to get
gRPC requests data from some HTTP servers clients. Can be used to
analyze incoming gRPC requests data, and to simulate web applications
with static responses. Based on python `grpcio` and `asyncio` frameworks.

### Requirements

Installed Python 3 interpreter. The interpreter must be accessible
from the console. Installed python pip package manager.

### Usage

`cap-grpc --help` - view help page

`cap-grpc` - start servers described in default config file `cap.yml` (this
file should be created and described manually)

`cap-grpc -c your_config_file.yml` - start servers described in
`your_config_file.yml`

### Configuration file

Configuration file is used to describe all gRPC servers
configurations. You can configure:
- gRPC server sockets, server .proto files, SSL/TLS certificates for
sockets
- gRPC responses mocks: output responses data in any format,
error status code, error message, response metadata
- enable gRPC proxy mode for specific endpoints
- HTTP response status code, headers and body. These parameters are
used by servers to create HTTP response on some request
- general and API requests-responses logging config. This is
a part of parameters that manages viewing and saving all gRPC requests
data. You can configure logging format, properties to view and
saving body to files and others

Configuration file example:

/home/my-user/book-service.proto:
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

/home/my-user/book-service-mock.yml:
```yaml
servers:
  - alias: 'Book API'
    sockets:
      - socket: 'localhost:8100'
      - socket: 'localhost:8200'
    reflection_enabled: true
    proto_files:
      - "book-service.proto"
    mocks:
      com.book.BookService:
        GetBook:
          value:
            id: 10
            name: "The Dictionary of Demons: Expanded and Revised: Names of the Damned"
            type: "ENCYCLOPEDIA"
            author:
              first_name: "Michael"
              last_name: "Belanger"
          metadata:
            custom_metadata: metadata
        AddBook:
          error:
            code: 16
            details: "Unauthorized. Credentials required"
        GetBooksList:
          proxy: 
            socket: "original-book-service-host:8100"
            seconds_timeout: 10
```

### Download

Tool can be downloaded from current repository's directory `dist`:
 - `cap-grpc` - executable file for Linux based systems
 - `cap-grpc.exe` - executable file for Windows based systems
