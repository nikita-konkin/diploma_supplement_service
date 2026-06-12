package edu.university.xlsxpivot;

import java.util.Map;

/**
 * Produces diploma XML from uploaded files and form parameters.
 */
@FunctionalInterface
public interface XmlEngine {

    byte[] generate(Map<String, byte[]> files, Map<String, String> params)
        throws Exception;
}
