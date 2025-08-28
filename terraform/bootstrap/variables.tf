variable "aws_profile" {
  description = "named AWS profile. drives account targeting and the env label."
  type        = string
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}
