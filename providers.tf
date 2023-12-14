terraform {
  required_providers {
    juju = {
      source  = "juju/juju"
      version = "0.9.1"
    }
    random = {
      source = "hashicorp/random"
      version = "3.6.0"
    }
  }
}
