terraform {
  required_providers {
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}

resource "null_resource" "server_1" {
  triggers = {
    name = "web-server"
  }
}

resource "null_resource" "server_2" {
  triggers = {
    name = "db-server"
  }
}