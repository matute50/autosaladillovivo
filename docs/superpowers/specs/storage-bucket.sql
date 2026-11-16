-- CREAR BUCKET video-factory-assets (500 MB, publico)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'video-factory-assets',
  'video-factory-assets',
  true,
  524288000,
  ARRAY['image/*', 'video/mp4', 'video/webm']
)
ON CONFLICT (id) DO NOTHING;

-- Politicas RLS para storage.objects del bucket
DROP POLICY IF EXISTS "public_read_video_factory_assets" ON storage.objects;
CREATE POLICY "public_read_video_factory_assets"
  ON storage.objects FOR SELECT
  TO public
  USING (bucket_id = 'video-factory-assets');

DROP POLICY IF EXISTS "auth_insert_video_factory_assets" ON storage.objects;
CREATE POLICY "auth_insert_video_factory_assets"
  ON storage.objects FOR INSERT
  TO authenticated
  WITH CHECK (bucket_id = 'video-factory-assets');

DROP POLICY IF EXISTS "auth_update_video_factory_assets" ON storage.objects;
CREATE POLICY "auth_update_video_factory_assets"
  ON storage.objects FOR UPDATE
  TO authenticated
  USING (bucket_id = 'video-factory-assets')
  WITH CHECK (bucket_id = 'video-factory-assets');

DROP POLICY IF EXISTS "auth_delete_video_factory_assets" ON storage.objects;
CREATE POLICY "auth_delete_video_factory_assets"
  ON storage.objects FOR DELETE
  TO authenticated
  USING (bucket_id = 'video-factory-assets');