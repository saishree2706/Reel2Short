import requests

MEDIA_URL = "https://instagram.fvga2-2.fna.fbcdn.net/o1/v/t16/f2/m84/AQP5Bqel-qJAj3KMllKVrJCIzdbizGrKwtdDoS_nh4x0rgCE-HFvI0BH5zYV1-f_-vw3zKcrTPpsjFvcUdRaN_xm1WGXb8S2iBWL828.mp4?_nc_cat=104&_nc_oc=AdrMuoVS52e5aU-t5sZAnlxYOripu-V2Nlgk3R2Iau3RhJgQEhJIRjmyTY-Pl6HmFufHvIxxZDlp_AxQukCp9Orm&_nc_sid=5e9851&_nc_ht=instagram.fvga2-2.fna.fbcdn.net&_nc_ohc=2nHvcKepLFcQ7kNvwFU_ZYO&efg=eyJ2ZW5jb2RlX3RhZyI6Inhwdl9wcm9ncmVzc2l2ZS5JTlNUQUdSQU0uQ0xJUFMuQzMuNzIwLmRhc2hfYmFzZWxpbmVfMV92MSIsInhwdl9hc3NldF9pZCI6NDM4MDQ5MTE1ODg3NzQ0OCwiYXNzZXRfYWdlX2RheXMiOjgsInZpX3VzZWNhc2VfaWQiOjEwODI3LCJkdXJhdGlvbl9zIjozMSwidXJsZ2VuX3NvdXJjZSI6Ind3dyJ9&ccb=17-1&vs=e3f5a8f7ef63507e&_nc_vs=HBksFQIYTGlnX2JhY2tmaWxsX3RpbWVsaW5lX3ZvZC9DRTQxMDYzQUJFODZEMDg2QzgwOEJDM0U4OUJGQzM5OV92aWRlb19kYXNoaW5pdC5tcDQVAALIARIAFQIYUWlnX3hwdl9wbGFjZW1lbnRfcGVybWFuZW50X3YyLzEyNEYwQUU0N0ZGN0U4QUI5RkVCN0EwOENGNUUwREE1X2F1ZGlvX2Rhc2hpbml0Lm1wNBUCAsgBEgAoABgAGwKIB3VzZV9vaWwBMRJwcm9ncmVzc2l2ZV9yZWNpcGUBMRUAACaQ1Lu3koLIDxUCKAJDMywXQD8AAAAAAAAYEmRhc2hfYmFzZWxpbmVfMV92MREAdf4HZZapAQA&_nc_gid=v-SUJGN9uzCagcXEIk9x5g&edm=ANo9K5cEAAAA&_nc_map=urlgen_bucketless&_nc_zt=28&_nc_tpa=Q5bMBQJpi4X3cUP2jcIls3JFPo1LlRoCtDlsFHR6_x1ml9tZGeB1K7vCnqJwcaHYoc_3OIHjJw3AYn0LNg&oh=00_AQIiEBEa6rmuCuIXxQdnLD0vjszr-0wl85YXbNTvmoxjqQ&oe=6A9F2690"

output_file = "instagram_reel.mp4"

print("Downloading video...")

response = requests.get(MEDIA_URL, stream=True, timeout=60)
response.raise_for_status()

with open(output_file, "wb") as file:
    for chunk in response.iter_content(chunk_size=1024 * 1024):
        if chunk:
            file.write(chunk)

print(f"Downloaded successfully: {output_file}")