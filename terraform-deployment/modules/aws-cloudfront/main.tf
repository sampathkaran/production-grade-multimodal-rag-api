resource "aws_cloudfront_distribution" "cfdist" {
    enabled = true 
    comment = "${var.project_name}-${var.environment}-api-cdn"

    origin {
        domain_name = var.alb_dns_name
        origin_id = "alb-origin"

        custom_origin_config {
          http_port = 80
          https_port = 443
          origin_protocol_policy = "http-only"
          origin_ssl_protocols = ["TLSv1.2"]
        }
    }

    default_cache_behavior {
      target_origin_id = "alb-origin"
      viewer_protocol_policy = "redirect-to-https"
      allowed_methods = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
      cached_methods           = ["GET", "HEAD"]

      cache_policy_id          = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"   # UseOriginCacheControlHeaders (managed)
      origin_request_policy_id = "b689b0a8-53d0-40ab-baf2-68738e2966ac"  
      
      compress = true
    }
    restrictions {
     geo_restriction {
      restriction_type = "none"    # Restrict viewer access: No
    }
  }

    viewer_certificate {
      cloudfront_default_certificate = true   # using *.cloudfront.net cert for now — swap for ACM cert + custom domain later
    }

    tags = {
       Name = "${var.project_name}-${var.environment}-api-cdn"
  }

}

data "aws_cloudfront_cache_policy" "use_origin_cache_headers" {
  name = "UseOriginCacheControlHeaders"
}

data "aws_cloudfront_origin_request_policy" "all_viewer_except_host" {
  name = "Managed-AllViewerExceptHostHeader"
}

