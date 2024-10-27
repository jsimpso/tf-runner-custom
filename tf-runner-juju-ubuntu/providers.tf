terraform {
  required_version = ">= 1.6.6"
  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 2.1.0"
    }
    vault = {
      source  = "hashicorp/vault"
      version = "~> 4.4.0"
    }
    ldap = {
      source  = "elastic-infra/ldap"
      version = "~> 2.0.1"
    }
    juju = {
      source  = "juju/juju"
      version = "~> 0.15.0"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.12.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6.0"
    }
    github = {
      source  = "integrations/github"
      version = "~> 6.2.0"
    }
    external = {
      source  = "hashicorp/external"
      version = "~> 2.3.3"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0.5"
    }
  }
}
