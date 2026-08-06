-- Enforce the Catalogue Vault upload ceiling at the storage service itself.
-- The API validates the declared size for a friendly error, while this bucket
-- limit prevents clients from understating the size and uploading a larger
-- object through a signed URL.
update storage.buckets
set file_size_limit = 524288000
where id = 'catalogue';
