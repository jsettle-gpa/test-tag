SELECT
	    st.shift_template_id AS shiftTemplateId,
	    st.title             AS title,
	
	    CAST(
	        DATEDIFF_BIG(
	            MILLISECOND,
	            '1970-01-01T00:00:00+00:00',
	            CAST(st.start_datetime_utc AS DATETIMEOFFSET)
	        ) AS varchar(20)
	    ) AS startDatetimeUtc,
	
	    CAST(
	        DATEDIFF_BIG(
	            MILLISECOND,
	            '1970-01-01T00:00:00+00:00',
	            CAST(st.end_datetime_utc AS DATETIMEOFFSET)
	        ) AS varchar(20)
	    ) AS endDatetimeUtc,
	
	    st.duration_minutes    AS durationMinutes,
	    st.rrule               AS rrule,
	    CONVERT(char(10), st.recurrence_end_date, 23) AS recurrenceEndDate,
	    st.metadata            AS metadata,
	    core.asset.asset_id    AS assetId,
	    operation.asset_shift_assignment.asset_shift_assignment_id AS assetShiftAssignmentId

FROM 	core.asset
		INNER JOIN operation.asset_shift_assignment
		    ON core.asset.asset_id = operation.asset_shift_assignment.asset_id
		INNER JOIN operation.shift_template AS st
		    ON operation.asset_shift_assignment.shift_template_id = st.shift_template_id
WHERE 	core.asset.asset_id = :assetId
  		AND operation.asset_shift_assignment.is_enabled = 1;