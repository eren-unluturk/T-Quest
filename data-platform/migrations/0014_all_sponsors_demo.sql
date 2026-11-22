-- Every sponsor and store in this project is a demo placeholder (we are not pursuing real partnerships).
-- The dev seed rows predate the flag and defaulted to false; fix them and make true the default.
UPDATE sponsors SET demo_placeholder = true WHERE demo_placeholder IS DISTINCT FROM true;
UPDATE stores   SET demo_placeholder = true WHERE demo_placeholder IS DISTINCT FROM true;
ALTER TABLE sponsors ALTER COLUMN demo_placeholder SET DEFAULT true;
ALTER TABLE stores   ALTER COLUMN demo_placeholder SET DEFAULT true;
