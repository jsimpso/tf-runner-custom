terraform {
  required_version = ">= 1.6.6"
  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 1.49.0"
    }
    vault = {
      source  = "hashicorp/vault"
      version = "~> 3.12.0"
    }
    ldap = {
      source  = "elastic-infra/ldap"
      version = "~> 2.0"
    }
    juju = {
      source  = "juju/juju"
      version = "~> 0.10.1"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.9.1"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5.1"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0.5"
    }
  }
}
