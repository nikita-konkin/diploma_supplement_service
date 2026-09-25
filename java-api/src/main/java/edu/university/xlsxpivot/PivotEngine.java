package edu.university.xlsxpivot;

import java.io.IOException;

/**
 * Produces a pivot workbook from the statement and the discipline list,
 * taking credits from the curriculum when it is given.
 */
@FunctionalInterface
public interface PivotEngine {

    /**
     * Build the pivot.
     *
     * @param scores Statement with grades
     * @param disciplines Discipline list
     * @param curriculum Curriculum, the source of credits; null if not uploaded
     */
    byte[] processPivot(Upload scores, Upload disciplines, Upload curriculum) throws IOException;
}
