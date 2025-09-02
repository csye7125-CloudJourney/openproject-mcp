# 3-AZ layout: public + private + intra per AZ. intra subnets have no
# route to the internet, which is what RDS and MSK sit behind.

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs        = slice(data.aws_availability_zones.available.names, 0, 3)
  newbits    = 4
  public_idx = [0, 1, 2]
  priv_idx   = [3, 4, 5]
  intra_idx  = [6, 7, 8]
}

resource "aws_subnet" "public" {
  count             = length(local.azs)
  vpc_id            = aws_vpc.this.id
  availability_zone = local.azs[count.index]
  cidr_block        = cidrsubnet(var.cidr_block, local.newbits, local.public_idx[count.index])

  map_public_ip_on_launch = true

  tags = merge(var.tags, {
    Name = "${var.name}-public-${local.azs[count.index]}"
    Tier = "public"
  })
}

resource "aws_subnet" "private" {
  count             = length(local.azs)
  vpc_id            = aws_vpc.this.id
  availability_zone = local.azs[count.index]
  cidr_block        = cidrsubnet(var.cidr_block, local.newbits, local.priv_idx[count.index])

  tags = merge(var.tags, {
    Name = "${var.name}-private-${local.azs[count.index]}"
    Tier = "private"
  })
}

resource "aws_subnet" "intra" {
  count             = length(local.azs)
  vpc_id            = aws_vpc.this.id
  availability_zone = local.azs[count.index]
  cidr_block        = cidrsubnet(var.cidr_block, local.newbits, local.intra_idx[count.index])

  tags = merge(var.tags, {
    Name = "${var.name}-intra-${local.azs[count.index]}"
    Tier = "intra"
  })
}
