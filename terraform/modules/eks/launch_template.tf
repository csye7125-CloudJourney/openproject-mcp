# launch template to actually plumb kube-reserved + system-reserved into
# the kubelet. without a launch template the node groups above use the
# EKS-managed default AMI which never reads kubelet_extra_args. had this
# declared but unused for half a day before i caught it.
#
# uses the EKS-optimized AMI via bootstrap.sh: override user_data to
# call /etc/eks/bootstrap.sh with --kubelet-extra-args.

data "aws_ssm_parameter" "eks_ami" {
  name = "/aws/service/eks/optimized-ami/${var.kubernetes_version}/amazon-linux-2/recommended/image_id"
}

locals {
  user_data = base64encode(<<-EOT
    #!/bin/bash
    set -o xtrace
    /etc/eks/bootstrap.sh ${aws_eks_cluster.this.name} \
      --kubelet-extra-args '${local.kubelet_extra_args}'
  EOT
  )
}

resource "aws_launch_template" "ondemand" {
  name_prefix   = "${var.name}-ondemand-"
  image_id      = data.aws_ssm_parameter.eks_ami.value
  instance_type = var.ondemand_instance_type
  user_data     = local.user_data

  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  tag_specifications {
    resource_type = "instance"
    tags = merge(var.tags, {
      Name = "${var.name}-ondemand-node"
    })
  }
}

resource "aws_launch_template" "spot" {
  name_prefix = "${var.name}-spot-"
  image_id    = data.aws_ssm_parameter.eks_ami.value
  user_data   = local.user_data

  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  tag_specifications {
    resource_type = "instance"
    tags = merge(var.tags, {
      Name = "${var.name}-spot-node"
    })
  }
}
