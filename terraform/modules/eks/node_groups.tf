# two managed node groups. on-demand pool for steady-state workloads
# (mcp-server, observability); spot pool for batch/burst (k6 runs, chaos).
#
# kube-reserved + system-reserved set explicitly. without these the
# system daemons starve under load. found this the hard way during a
# load test where kubelet stopped responding right as we hit peak rps.

data "aws_iam_policy_document" "node_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "node" {
  name               = "${var.name}-eks-node"
  assume_role_policy = data.aws_iam_policy_document.node_assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "node" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
    "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
  ])
  role       = aws_iam_role.node.name
  policy_arn = each.value
}

locals {
  # cpu=100m + memory=512Mi for each of kube-reserved and system-reserved.
  # eviction at 10% mem / 5% nodefs is aggressive; matches what stopped
  # the OOM-kill loop on the t3.medium pool.
  kubelet_extra_args = "--kube-reserved=cpu=100m,memory=512Mi --system-reserved=cpu=100m,memory=512Mi --eviction-hard=memory.available<10%,nodefs.available<5%"
}

resource "aws_eks_node_group" "ondemand" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${var.name}-ondemand"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.private_subnet_ids

  capacity_type = "ON_DEMAND"

  launch_template {
    id      = aws_launch_template.ondemand.id
    version = aws_launch_template.ondemand.latest_version
  }

  scaling_config {
    desired_size = var.ondemand_desired_size
    min_size     = var.ondemand_min_size
    max_size     = var.ondemand_max_size
  }

  update_config {
    max_unavailable_percentage = 33
  }

  labels = {
    "node.kubernetes.io/lifecycle" = "ondemand"
    "workload-class"               = "steady"
  }

  tags = merge(var.tags, {
    Name = "${var.name}-ondemand-ng"
  })

  depends_on = [aws_iam_role_policy_attachment.node]
}

resource "aws_eks_node_group" "spot" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${var.name}-spot"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.private_subnet_ids

  capacity_type  = "SPOT"
  instance_types = var.spot_instance_types

  launch_template {
    id      = aws_launch_template.spot.id
    version = aws_launch_template.spot.latest_version
  }

  scaling_config {
    desired_size = var.spot_desired_size
    min_size     = var.spot_min_size
    max_size     = var.spot_max_size
  }

  update_config {
    max_unavailable_percentage = 50
  }

  labels = {
    "node.kubernetes.io/lifecycle" = "spot"
    "workload-class"               = "burst"
  }

  taint {
    key    = "spot"
    value  = "true"
    effect = "NO_SCHEDULE"
  }

  tags = merge(var.tags, {
    Name = "${var.name}-spot-ng"
  })

  depends_on = [aws_iam_role_policy_attachment.node]
}
