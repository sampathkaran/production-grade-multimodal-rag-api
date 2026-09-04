output "cloudfront_domain_name" {
  value = aws_cloudfront_distribution.cfdist.domain_name
}