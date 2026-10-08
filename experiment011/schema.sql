PRAGMA foreign_keys = ON;
CREATE TABLE dataset(version TEXT PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE, manifest TEXT NOT NULL);
CREATE TABLE source(dataset_version TEXT NOT NULL REFERENCES dataset(version), id TEXT NOT NULL,
 title TEXT NOT NULL, url TEXT NOT NULL, accessed TEXT NOT NULL, rights TEXT NOT NULL, record TEXT NOT NULL,
 PRIMARY KEY(dataset_version,id));
CREATE TABLE element(dataset_version TEXT NOT NULL, symbol TEXT NOT NULL, atomic_number INTEGER NOT NULL CHECK(atomic_number>0),
 source_id TEXT NOT NULL, record TEXT NOT NULL, PRIMARY KEY(dataset_version,symbol), UNIQUE(dataset_version,atomic_number),
 FOREIGN KEY(dataset_version,source_id) REFERENCES source(dataset_version,id));
CREATE TABLE isotope(dataset_version TEXT NOT NULL, element_symbol TEXT NOT NULL, mass_number INTEGER NOT NULL CHECK(mass_number>0),
 source_id TEXT NOT NULL, record TEXT NOT NULL, PRIMARY KEY(dataset_version,element_symbol,mass_number),
 FOREIGN KEY(dataset_version,element_symbol) REFERENCES element(dataset_version,symbol),
 FOREIGN KEY(dataset_version,source_id) REFERENCES source(dataset_version,id));
CREATE TABLE material(dataset_version TEXT NOT NULL, id TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('metal','alloy','compound','other')),
 source_id TEXT NOT NULL, record TEXT NOT NULL, PRIMARY KEY(dataset_version,id),
 FOREIGN KEY(dataset_version,source_id) REFERENCES source(dataset_version,id));
CREATE TABLE property(dataset_version TEXT NOT NULL, material_id TEXT NOT NULL, name TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('reference_measurement','reference_nominal','approximation','unknown')),
 units TEXT NOT NULL, source_id TEXT, conditions TEXT NOT NULL, uncertainty TEXT NOT NULL, record TEXT NOT NULL,
 PRIMARY KEY(dataset_version,material_id,name), FOREIGN KEY(dataset_version,material_id) REFERENCES material(dataset_version,id),
 FOREIGN KEY(dataset_version,source_id) REFERENCES source(dataset_version,id), CHECK(status='unknown' OR source_id IS NOT NULL));
CREATE TABLE constant(dataset_version TEXT NOT NULL, id TEXT NOT NULL, source_id TEXT NOT NULL, units TEXT NOT NULL,
 record TEXT NOT NULL, PRIMARY KEY(dataset_version,id), FOREIGN KEY(dataset_version,source_id) REFERENCES source(dataset_version,id));
