terraform {
  required_version = ">= 1.6.6"
  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 3.3.2"
    }
    vault = {
      source  = "hashicorp/vault"
      version = "~> 5.3.0"
    }
    ldap = {
      source  = "elastic-infra/ldap"
      version = "~> 2.0.1"
    }
    juju = {
      source  = "juju/juju"
      version = "~> 0.22.0"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.13.1"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.7.2"
    }
    github = {
      source  = "integrations/github"
      version = "~> 6.6.0"
    }
    external = {
      source  = "hashicorp/external"
      version = "~> 2.3.5"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.1.0"
    }
  }
}
