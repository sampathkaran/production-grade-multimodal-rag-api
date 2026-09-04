output "public_subnet_ids"{
   description = "The ID of the subnets" 
   value = {for k,v in aws_subnet.public_subnet : k => v.id }
}


output "private_subnet_ids"{
   description = "The ID of the subnets" 
   value = {for k,v in aws_subnet.private_subnet: k => v.id }
}






